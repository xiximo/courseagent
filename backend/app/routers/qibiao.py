from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.session import get_db
from app.review.service import ReviewAssistService
from app.review.sse import format_sse_event
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.review import AnalyzeDraftBody, DraftAnalysisResultDto
from app.schemas.review_report import ExportReportBody, GenerateReportBody, ReviewReportDto
from app.review.export.service import export_review_report
from app.review.report_store import ReviewReportStore
from app.review.report_synthesis import ReportSynthesisService
from app.schemas.review_task import ReviewTaskDto
from app.review_tasks.service import ReviewTaskService
from app.schemas.agent import AgentOverviewDto
from app.schemas.standard import StandardDetailDto, StandardSearchPageResult
from app.services.agent_overview import AgentOverviewService
from app.services.llm_settings import get_or_create_llm_config
from app.services.standards import StandardsService

router = APIRouter(prefix="/api/v1/qibiao", tags=["qibiao"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _created_by_label(user: AuthUserProfile) -> str:
    return user.fullName or user.username or user.id


def _created_by_user_id(user: AuthUserProfile) -> uuid.UUID | None:
    try:
        return uuid.UUID(user.id)
    except ValueError:
        return None


async def _read_analyze_input(request: Request) -> tuple[str | None, bytes | None, str | None]:
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is not None and hasattr(upload, "read"):
            payload = await upload.read()
            filename = getattr(upload, "filename", None) or "draft.docx"
            return None, payload, filename

        pasted = str(form.get("text") or "").strip()
        if pasted:
            return pasted, None, str(form.get("fileName") or "")
        return None, None, None

    raw = await request.json()
    body = AnalyzeDraftBody.model_validate(raw)
    if body.text and body.text.strip():
        return body.text.strip(), None, body.fileName
    return None, None, None


def _not_implemented(feature: str) -> None:
    raise ApiBusinessError(
        "NOT_IMPLEMENTED",
        f"{feature} 尚未实现，请继续使用前端 Mock 或等待后续迭代",
        501,
    )


@router.get("/standards", response_model=ApiResponse[StandardSearchPageResult])
def search_standards(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    standardNo: str | None = Query(default=None),
    name: str | None = Query(default=None),
    standardType: Literal["domestic", "foreign"] | None = Query(default=None),
    status: Literal["active", "obsolete", "draft"] | None = Query(default=None),
    partCode: str | None = Query(default=None),
    country: str | None = Query(default=None),
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = StandardsService(db)
    return success(
        service.search(
            page=page,
            page_size=pageSize,
            standard_no=standardNo,
            name=name,
            standard_type=standardType,
            status=status,
            part_code=partCode,
            country=country,
        )
    )


@router.get("/standards/{standard_id}", response_model=ApiResponse[StandardDetailDto])
def get_standard_detail(
    standard_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(standard_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "标准 ID 无效", 400) from exc

    service = StandardsService(db)
    detail = service.get_detail(parsed_id)
    if detail is None:
        raise ApiBusinessError("NOT_FOUND", "未查询到符合条件的标准", 404)
    return success(detail)


@router.post("/review-assist/analyze", response_model=ApiResponse[DraftAnalysisResultDto])
async def analyze_draft(
    request: Request,
    user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    llm_config = get_or_create_llm_config(db)
    service = ReviewAssistService(db, llm_config)
    text, file_bytes, file_name = await _read_analyze_input(request)
    analyze_kwargs = {
        "created_by": _created_by_label(user),
        "created_by_user_id": _created_by_user_id(user),
    }

    if file_bytes:
        return success(
            service.analyze(
                file_bytes=file_bytes,
                file_name=file_name,
                **analyze_kwargs,
            )
        )
    if text:
        return success(
            service.analyze(text=text, file_name=file_name, **analyze_kwargs)
        )

    raise ApiBusinessError(
        "DRAFT_UNRECOGNIZED",
        "请上传 Word 文件或粘贴草案文本",
        400,
    )


@router.post("/review-assist/analyze/stream")
async def analyze_draft_stream(
    request: Request,
    user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    llm_config = get_or_create_llm_config(db)
    service = ReviewAssistService(db, llm_config)
    text, file_bytes, file_name = await _read_analyze_input(request)

    if not file_bytes and not text:
        raise ApiBusinessError(
            "DRAFT_UNRECOGNIZED",
            "请上传 Word 文件或粘贴草案文本",
            400,
        )

    created_by = _created_by_label(user)
    created_by_user_id = _created_by_user_id(user)

    def event_stream():
        yield format_sse_event("ping", {"status": "started"})
        for event, data in service.iter_analyze_events(
            text=text,
            file_bytes=file_bytes,
            file_name=file_name,
            created_by=created_by,
            created_by_user_id=created_by_user_id,
        ):
            yield format_sse_event(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            **SSE_HEADERS,
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post("/review-assist/report/generate", response_model=ApiResponse[ReviewReportDto])
def generate_review_report(
    body: GenerateReportBody,
    user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    llm_config = get_or_create_llm_config(db)
    service = ReportSynthesisService(db, llm_config)
    report = service.synthesize(
        analysis=body.analysis,
        draft_excerpt=body.draftExcerpt,
        parse_note=body.parseNote,
    )
    report = ReviewReportStore(db).save(
        report,
        created_by=_created_by_label(user),
        created_by_user_id=_created_by_user_id(user),
    )
    return success(report)


@router.get(
    "/review-assist/report/by-source/{source_task_id}",
    response_model=ApiResponse[ReviewReportDto],
)
def get_review_report_by_source_task(
    source_task_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = ReviewReportStore(db).get_by_source_task_id(source_task_id)
    if report is None:
        raise ApiBusinessError("NOT_FOUND", "未找到评审报告", 404)
    return success(report)


@router.get(
    "/review-assist/report/{report_id}",
    response_model=ApiResponse[ReviewReportDto],
)
def get_review_report(
    report_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = ReviewReportStore(db).get_by_id(report_id)
    if report is None:
        raise ApiBusinessError("NOT_FOUND", "未找到评审报告", 404)
    return success(report)


@router.post("/review-assist/report/export")
def export_review_report_file(
    body: ExportReportBody,
    export_format: Literal["docx", "pptx"] = Query(..., alias="format"),
    _user: AuthUserProfile = Depends(get_current_user),
):
    from urllib.parse import quote

    content, media_type, filename = export_review_report(body.report, export_format)
    ascii_fallback = f"review_report.{export_format}"
    disposition = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


@router.post("/review-assist/sessions/{session_id}/messages")
def send_review_message(session_id: str):
    _not_implemented("审核辅助追问")


@router.get("/review-tasks", response_model=ApiResponse[list[ReviewTaskDto]])
def list_review_tasks(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReviewTaskService(db)
    return success(service.list_tasks())


@router.post("/review-tasks", response_model=ApiResponse[ReviewTaskDto])
async def create_review_task(
    request: Request,
    user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise ApiBusinessError(
            "INVALID_REQUEST",
            "请使用 multipart/form-data 上传 Word 文档",
            400,
        )

    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise ApiBusinessError("MISSING_FILE", "请上传 Word 文档", 400)

    file_bytes = await upload.read()
    file_name = getattr(upload, "filename", None) or "draft.docx"
    remark = str(form.get("remark") or "").strip() or None

    service = ReviewTaskService(db)
    return success(
        service.create_task(
            file_name=file_name,
            file_bytes=file_bytes,
            remark=remark,
            user=user,
        )
    )


@router.get("/agent/overview", response_model=ApiResponse[AgentOverviewDto])
def agent_overview(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = AgentOverviewService(db)
    return success(service.build_overview())


@router.get("/agent/profiles")
def list_agent_profiles():
    _not_implemented("Agent Profile")


@router.put("/agent/profiles")
def update_agent_profiles():
    _not_implemented("更新 Agent Profile")


@router.get("/agent/orchestration")
def get_orchestration():
    _not_implemented("编排参数")


@router.put("/agent/orchestration")
def update_orchestration():
    _not_implemented("更新编排参数")


@router.get("/agent/tools")
def list_agent_tools():
    _not_implemented("Tool Registry")


@router.get("/agent/tools/{tool_id}")
def get_agent_tool(tool_id: str):
    _not_implemented("Tool 详情")


@router.get("/agent/toolsets")
def get_toolsets():
    _not_implemented("Toolset 矩阵")


@router.put("/agent/toolsets")
def update_toolsets():
    _not_implemented("更新 Toolset 矩阵")


@router.get("/agent/skills")
def list_agent_skills():
    _not_implemented("Skills 列表")


@router.get("/agent/skills/{skill_id}")
def get_agent_skill(skill_id: str):
    _not_implemented("Skill 详情")


@router.post("/agent/skills/{skill_id}/activate")
def activate_agent_skill(skill_id: str):
    _not_implemented("激活 Skill")


@router.get("/agent/models")
def get_model_routing():
    _not_implemented("模型路由")


@router.put("/agent/models")
def update_model_routing():
    _not_implemented("更新模型路由")


@router.get("/agent/sessions")
def list_agent_sessions():
    _not_implemented("Agent 会话列表")


@router.get("/agent/sessions/{session_id}/trace")
def get_agent_session_trace(session_id: str):
    _not_implemented("Agent 会话轨迹")
