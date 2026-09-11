from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, parse_user_uuid
from app.api.errors import ApiBusinessError
from app.course_agent.material_service import MaterialService
from app.course_agent.model_service import ModelService
from app.course_agent.service import CourseAgentService
from app.db.session import get_db
from app.review.sse import format_sse_event
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.course_agent import (
    AdminSessionDetailDto,
    AdminUserSessionGroupDto,
    CourseAgentConfigDto,
    CourseAgentKnowledgeBaseDto,
    CourseAgentLeadDetailDto,
    CourseAgentLeadSummaryDto,
    CourseAgentModelProfileDto,
    CourseAgentPatchBody,
    CourseAgentSessionDto,
    CourseAgentSessionSummaryDto,
    CourseAgentSummaryDto,
    CourseMaterialActionResultDto,
    CourseMaterialDocumentDto,
    CreateCourseAgentBody,
    CreateCourseKnowledgeBaseBody,
    CreateCourseModelBody,
    DeleteCourseAgentLeadResultDto,
    DeleteCourseAgentResultDto,
    DeleteCourseAgentSessionResultDto,
    DeleteCourseKnowledgeBaseResultDto,
    DeleteCourseModelResultDto,
    PublicAgentConfigDto,
    SendCourseAgentMessageBody,
    UpdateCourseKnowledgeBaseBody,
    UpdateCourseModelBody,
)
from app.schemas.processing import AttachmentExtractedTextDto
from app.services.billing import (
    require_agent_type_for_plan,
    require_knowledge_base_quota,
    require_pro_plan,
)
from app.services.tenant_scope import resolve_tenant_scope
from app.services.users import get_user_by_id

router = APIRouter(tags=["course-agent"])

_ADMIN_ROLES = {"sys_admin", "system_admin", "admin", "org_admin"}


def _require_admin(
    user: AuthUserProfile = Depends(get_current_user),
) -> AuthUserProfile:
    codes = {code.lower() for code in user.roleCodes}
    if not (codes & _ADMIN_ROLES):
        raise ApiBusinessError("FORBIDDEN", "仅管理员可查看会话记录", 403)
    return user


def _require_knowledge_admin(
    user: AuthUserProfile = Depends(get_current_user),
) -> AuthUserProfile:
    return _require_admin(user)


def _agent_service(db: Session, user: AuthUserProfile) -> CourseAgentService:
    service = CourseAgentService(db, scope=resolve_tenant_scope(user))
    service.ensure_workspace()
    return service


def _material_service(db: Session, user: AuthUserProfile) -> MaterialService:
    return MaterialService(db, scope=resolve_tenant_scope(user))

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _parse_uuid(value: str, *, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", f"{label}无效", 400) from exc


def _origin_from_request(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return origin
    referer = request.headers.get("referer")
    if referer:
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return None


def _client_ip_from_request(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip() or None
    if request.client and request.client.host:
        return request.client.host
    return None


def _visitor_from_request(request: Request):
    from app.course_agent.lead_service import VisitorContext

    return VisitorContext(
        client_ip=_client_ip_from_request(request),
        user_agent=request.headers.get("user-agent"),
        origin=_origin_from_request(request),
    )


# --- 管理端（需 JWT）---


@router.get("/api/v1/course-agents", response_model=ApiResponse[list[CourseAgentSummaryDto]])
def list_course_agents(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_agent_service(db, _user).list_agents())


@router.get(
    "/api/v1/course-agent/leads",
    response_model=ApiResponse[list[CourseAgentLeadSummaryDto]],
)
def list_course_agent_leads(
    agent_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(
        _agent_service(db, _user).list_leads(
            agent_id=agent_id, limit=limit, offset=offset
        )
    )


@router.get(
    "/api/v1/course-agent/leads/{lead_id}",
    response_model=ApiResponse[CourseAgentLeadDetailDto],
)
def get_course_agent_lead(
    lead_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(lead_id, label="线索 ID")
    return success(_agent_service(db, _user).get_lead(parsed))


@router.delete(
    "/api/v1/course-agent/leads/{lead_id}",
    response_model=ApiResponse[DeleteCourseAgentLeadResultDto],
)
def delete_course_agent_lead(
    lead_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(lead_id, label="线索 ID")
    return success(
        DeleteCourseAgentLeadResultDto(**_agent_service(db, _user).delete_lead(parsed))
    )


@router.get(
    "/api/v1/course-agent/session-records",
    response_model=ApiResponse[list[AdminUserSessionGroupDto]],
)
def list_admin_session_records(
    agent_id: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    _user: AuthUserProfile = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    return success(
        _agent_service(db, _user).list_admin_session_groups(
            agent_id, from_dt=from_time, to_dt=to_time
        )
    )


@router.get(
    "/api/v1/course-agent/session-records/{session_id}",
    response_model=ApiResponse[AdminSessionDetailDto],
)
def get_admin_session_record(
    session_id: str,
    _user: AuthUserProfile = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(_agent_service(db, _user).get_admin_session(parsed))


@router.delete(
    "/api/v1/course-agent/session-records/{session_id}",
    response_model=ApiResponse[DeleteCourseAgentSessionResultDto],
)
def delete_admin_session_record(
    session_id: str,
    _user: AuthUserProfile = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    _agent_service(db, _user).delete_admin_session(parsed)
    return success(DeleteCourseAgentSessionResultDto())


@router.post(
    "/api/v1/course-agents",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def create_course_agent(
    body: CreateCourseAgentBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_user_by_id(db, uuid.UUID(_user.id))
    require_agent_type_for_plan(account, db, body.agentType)
    return success(_agent_service(db, _user).create_agent(body))


@router.delete(
    "/api/v1/course-agents/{agent_id}",
    response_model=ApiResponse[DeleteCourseAgentResultDto],
)
def delete_course_agent(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(DeleteCourseAgentResultDto(**_agent_service(db, _user).delete_agent(agent_id)))


@router.get(
    "/api/v1/course-agents/{agent_id}",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def get_course_agent(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_agent_service(db, _user).get_agent(agent_id))


@router.patch(
    "/api/v1/course-agents/{agent_id}",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def patch_course_agent(
    agent_id: str,
    body: CourseAgentPatchBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_agent_service(db, _user).update_agent(agent_id, body))


@router.post(
    "/api/v1/course-agents/{agent_id}/set-default",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def set_default_course_agent(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_agent_service(db, _user).set_default_agent(agent_id))


@router.post(
    "/api/v1/course-agents/{agent_id}/schedule/run",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def run_course_agent_schedule(
    agent_id: str,
    _user: AuthUserProfile = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    account = get_user_by_id(db, uuid.UUID(_user.id))
    require_pro_plan(account, db=db)
    return success(_agent_service(db, _user).run_schedule_now(agent_id))


@router.get(
    "/api/v1/platform/knowledge-bases",
    response_model=ApiResponse[list[CourseAgentKnowledgeBaseDto]],
)
def list_platform_knowledge_bases(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_material_service(db, _user).list_all_knowledge_bases())


@router.post(
    "/api/v1/platform/knowledge-bases",
    response_model=ApiResponse[CourseAgentKnowledgeBaseDto],
)
def create_platform_knowledge_base(
    body: CreateCourseKnowledgeBaseBody,
    _user: AuthUserProfile = Depends(_require_knowledge_admin),
    db: Session = Depends(get_db),
):
    account = get_user_by_id(db, uuid.UUID(_user.id))
    require_knowledge_base_quota(db, account)
    return success(
        _material_service(db, _user).create_knowledge_base(
            name=body.name,
            description=body.description,
            chunk_mode=body.chunkMode,
            chunk_max_chars=body.chunkMaxChars,
            chunk_overlap_chars=body.chunkOverlapChars,
        )
    )


@router.get(
    "/api/v1/platform/knowledge-bases/{kb_id}",
    response_model=ApiResponse[CourseAgentKnowledgeBaseDto],
)
def get_platform_knowledge_base(
    kb_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_material_service(db, _user).get_knowledge_base(kb_id))


@router.patch(
    "/api/v1/platform/knowledge-bases/{kb_id}",
    response_model=ApiResponse[CourseAgentKnowledgeBaseDto],
)
def update_platform_knowledge_base(
    kb_id: str,
    body: UpdateCourseKnowledgeBaseBody,
    _user: AuthUserProfile = Depends(_require_knowledge_admin),
    db: Session = Depends(get_db),
):
    return success(
        _material_service(db, _user).update_knowledge_base(
            kb_id,
            name=body.name,
            description=body.description,
            chunk_mode=body.chunkMode,
            chunk_max_chars=body.chunkMaxChars,
            chunk_overlap_chars=body.chunkOverlapChars,
        )
    )


@router.delete(
    "/api/v1/platform/knowledge-bases/{kb_id}",
    response_model=ApiResponse[DeleteCourseKnowledgeBaseResultDto],
)
def delete_platform_knowledge_base(
    kb_id: str,
    _user: AuthUserProfile = Depends(_require_knowledge_admin),
    db: Session = Depends(get_db),
):
    _material_service(db, _user).delete_knowledge_base(kb_id)
    return success(DeleteCourseKnowledgeBaseResultDto())


@router.get(
    "/api/v1/platform/knowledge-bases/{kb_id}/documents",
    response_model=ApiResponse[list[CourseMaterialDocumentDto]],
)
def list_platform_knowledge_documents(
    kb_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material = _material_service(db, _user)
    kb = material.get_knowledge_base(kb_id)
    docs = material.list_material_documents(kb.materialLabel)
    return success([CourseMaterialDocumentDto.model_validate(item) for item in docs])


@router.post(
    "/api/v1/platform/knowledge-bases/{kb_id}/upload",
    response_model=ApiResponse[CourseMaterialActionResultDto],
)
async def upload_platform_knowledge_document(
    kb_id: str,
    request: Request,
    _user: AuthUserProfile = Depends(_require_knowledge_admin),
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise ApiBusinessError(
            "INVALID_REQUEST",
            "请使用 multipart/form-data 上传资料文件",
            400,
        )

    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise ApiBusinessError("MISSING_FILE", "请上传资料文件", 400)

    file_bytes = await upload.read()
    file_name = getattr(upload, "filename", None) or "document.pdf"
    material = _material_service(db, _user)
    kb = material.get_knowledge_base(kb_id)
    updated = material.upload_material(
        kb.materialLabel,
        file_name=file_name,
        file_bytes=file_bytes,
    )
    return success(
        CourseMaterialActionResultDto(
            materialLabel=kb.materialLabel,
            knowledgeBase=updated,
            message="资料已上传，正在后台抽取、切片并建立向量索引",
        )
    )


@router.delete(
    "/api/v1/platform/knowledge-bases/{kb_id}/documents/{attachment_id}",
    response_model=ApiResponse[CourseMaterialActionResultDto],
)
def delete_platform_knowledge_document(
    kb_id: str,
    attachment_id: str,
    _user: AuthUserProfile = Depends(_require_knowledge_admin),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(attachment_id, label="文档 ID")
    material = _material_service(db, _user)
    kb = material.get_knowledge_base(kb_id)
    updated = material.delete_material_document(kb.materialLabel, parsed)
    return success(
        CourseMaterialActionResultDto(
            materialLabel=kb.materialLabel,
            knowledgeBase=updated,
            message="文档已删除",
        )
    )


@router.post(
    "/api/v1/platform/knowledge-bases/{kb_id}/reindex",
    response_model=ApiResponse[CourseMaterialActionResultDto],
)
def reindex_platform_knowledge_base(
    kb_id: str,
    _user: AuthUserProfile = Depends(_require_knowledge_admin),
    db: Session = Depends(get_db),
):
    material = _material_service(db, _user)
    kb = material.get_knowledge_base(kb_id)
    updated = material.reindex_material(kb.materialLabel)
    return success(
        CourseMaterialActionResultDto(
            materialLabel=kb.materialLabel,
            knowledgeBase=updated,
            message="重建索引任务已启动",
        )
    )


@router.get(
    "/api/v1/platform/models",
    response_model=ApiResponse[list[CourseAgentModelProfileDto]],
)
def list_platform_models(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(ModelService(db).list_all_models())


@router.post(
    "/api/v1/platform/models",
    response_model=ApiResponse[CourseAgentModelProfileDto],
)
def create_platform_model(
    body: CreateCourseModelBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(ModelService(db).create_model(body))


@router.patch(
    "/api/v1/platform/models/{model_id}",
    response_model=ApiResponse[CourseAgentModelProfileDto],
)
def update_platform_model(
    model_id: str,
    body: UpdateCourseModelBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(ModelService(db).update_model(model_id, body))


@router.delete(
    "/api/v1/platform/models/{model_id}",
    response_model=ApiResponse[DeleteCourseModelResultDto],
)
def delete_platform_model(
    model_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(ModelService(db).delete_model(model_id))


@router.post(
    "/api/v1/platform/models/{model_id}/activate",
    response_model=ApiResponse[CourseAgentModelProfileDto],
)
def activate_platform_model(
    model_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(ModelService(db).set_active_model(model_id))


@router.post(
    "/api/v1/course-agents/{agent_id}/knowledge-bases",
    response_model=ApiResponse[CourseAgentKnowledgeBaseDto],
)
def create_course_knowledge_base(
    agent_id: str,
    body: CreateCourseKnowledgeBaseBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id  # 知识库为平台资源，不再挂靠 Agent
    account = get_user_by_id(db, uuid.UUID(_user.id))
    require_knowledge_base_quota(db, account)
    kb = _material_service(db, _user).create_knowledge_base(
        name=body.name,
        description=body.description,
        chunk_mode=body.chunkMode,
        chunk_max_chars=body.chunkMaxChars,
        chunk_overlap_chars=body.chunkOverlapChars,
    )
    return success(kb)


@router.get(
    "/api/v1/course-agents/{agent_id}/models",
    response_model=ApiResponse[list[CourseAgentModelProfileDto]],
)
def list_course_models(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    return success(ModelService(db).list_all_models())


@router.post(
    "/api/v1/course-agents/{agent_id}/models",
    response_model=ApiResponse[CourseAgentModelProfileDto],
)
def create_course_model(
    agent_id: str,
    body: CreateCourseModelBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    return success(ModelService(db).create_model(body))


@router.patch(
    "/api/v1/course-agents/{agent_id}/models/{model_id}",
    response_model=ApiResponse[CourseAgentModelProfileDto],
)
def update_course_model(
    agent_id: str,
    model_id: str,
    body: UpdateCourseModelBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    return success(ModelService(db).update_model(model_id, body))


@router.delete(
    "/api/v1/course-agents/{agent_id}/models/{model_id}",
    response_model=ApiResponse[DeleteCourseModelResultDto],
)
def delete_course_model(
    agent_id: str,
    model_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    return success(ModelService(db).delete_model(model_id))


@router.post(
    "/api/v1/course-agents/{agent_id}/models/{model_id}/activate",
    response_model=ApiResponse[CourseAgentModelProfileDto],
)
def activate_course_model(
    agent_id: str,
    model_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    return success(ModelService(db).set_active_model(model_id))


@router.patch(
    "/api/v1/course-agents/{agent_id}/knowledge-bases/{kb_id}",
    response_model=ApiResponse[CourseAgentKnowledgeBaseDto],
)
def update_course_knowledge_base(
    agent_id: str,
    kb_id: str,
    body: UpdateCourseKnowledgeBaseBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    kb = _material_service(db, _user).update_knowledge_base(
        kb_id,
        name=body.name,
        description=body.description,
        chunk_mode=body.chunkMode,
        chunk_max_chars=body.chunkMaxChars,
        chunk_overlap_chars=body.chunkOverlapChars,
    )
    return success(kb)


@router.delete(
    "/api/v1/course-agents/{agent_id}/knowledge-bases/{kb_id}",
    response_model=ApiResponse[DeleteCourseKnowledgeBaseResultDto],
)
def delete_course_knowledge_base(
    agent_id: str,
    kb_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    _material_service(db, _user).delete_knowledge_base(kb_id)
    return success(DeleteCourseKnowledgeBaseResultDto())


@router.get(
    "/api/v1/course-agents/{agent_id}/materials/{material_label}/documents",
    response_model=ApiResponse[list[CourseMaterialDocumentDto]],
)
def list_course_material_documents(
    agent_id: str,
    material_label: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    docs = _material_service(db, _user).list_material_documents(material_label)
    return success([CourseMaterialDocumentDto.model_validate(item) for item in docs])


@router.post(
    "/api/v1/course-agents/{agent_id}/materials/{material_label}/upload",
    response_model=ApiResponse[CourseMaterialActionResultDto],
)
async def upload_course_material(
    agent_id: str,
    material_label: str,
    request: Request,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise ApiBusinessError(
            "INVALID_REQUEST",
            "请使用 multipart/form-data 上传资料文件",
            400,
        )

    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise ApiBusinessError("MISSING_FILE", "请上传资料文件", 400)

    file_bytes = await upload.read()
    file_name = getattr(upload, "filename", None) or "document.pdf"

    kb = _material_service(db, _user).upload_material(
        material_label,
        file_name=file_name,
        file_bytes=file_bytes,
    )
    return success(
        CourseMaterialActionResultDto(
            materialLabel=material_label,
            knowledgeBase=kb,
            message="资料已上传，正在后台抽取、切片并建立向量索引",
        )
    )


@router.delete(
    "/api/v1/course-agents/{agent_id}/materials/{material_label}/documents/{attachment_id}",
    response_model=ApiResponse[CourseMaterialActionResultDto],
)
def delete_course_material_document(
    agent_id: str,
    material_label: str,
    attachment_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    parsed = _parse_uuid(attachment_id, label="文档 ID")
    kb = _material_service(db, _user).delete_material_document(material_label, parsed)
    return success(
        CourseMaterialActionResultDto(
            materialLabel=material_label,
            knowledgeBase=kb,
            message="文档已删除",
        )
    )


@router.post(
    "/api/v1/course-agents/{agent_id}/materials/{material_label}/reindex",
    response_model=ApiResponse[CourseMaterialActionResultDto],
)
def reindex_course_material(
    agent_id: str,
    material_label: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    del agent_id
    kb = _material_service(db, _user).reindex_material(material_label)
    return success(
        CourseMaterialActionResultDto(
            materialLabel=material_label,
            knowledgeBase=kb,
            message="重建索引任务已启动",
        )
    )


@router.post(
    "/api/v1/course-agents/{agent_id}/preview/sessions",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def create_preview_session(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_agent_service(db, _user).create_preview_session(agent_id))


@router.post(
    "/api/v1/course-agent/preview/sessions/{session_id}/messages",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def send_preview_message(
    session_id: str,
    body: SendCourseAgentMessageBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(_agent_service(db, _user).send_preview_message(parsed, body.content))


@router.post("/api/v1/course-agent/preview/sessions/{session_id}/messages/stream")
def send_preview_message_stream(
    session_id: str,
    body: SendCourseAgentMessageBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    service = _agent_service(db, _user)

    def event_stream():
        yield format_sse_event("ping", {"status": "started"})
        for event, data in service.iter_send_preview_message_events(parsed, body.content):
            yield format_sse_event(event, data if isinstance(data, dict) else {"data": data})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            **SSE_HEADERS,
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )

@router.post(
    "/api/v1/course-agent/preview/sessions/{session_id}/reset",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def reset_preview_session(
    session_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(_agent_service(db, _user).reset_preview_session(parsed))


def _require_user_id(user: AuthUserProfile) -> uuid.UUID:
    user_id = parse_user_uuid(user)
    if user_id is None:
        raise ApiBusinessError("UNAUTHORIZED", "用户不存在或已失效", 401)
    return user_id


# --- 对话 API（需登录）---


@router.get(
    "/api/v1/course-agents/{agent_id}/public-config",
    response_model=ApiResponse[PublicAgentConfigDto],
)
def get_public_agent_config(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_agent_service(db, _user).get_public_config(agent_id))


@router.get(
    "/api/v1/course-agent/attachments/{attachment_id}/extracted-text",
    response_model=ApiResponse[AttachmentExtractedTextDto],
)
def get_public_attachment_extracted_text(
    attachment_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(attachment_id, label="附件 ID")
    return success(_agent_service(db, _user).get_public_attachment_extracted_text(parsed))


@router.post(
    "/api/v1/course-agents/{agent_id}/sessions",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def create_public_session(
    agent_id: str,
    request: Request,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(
        _agent_service(db, _user).create_session(
            agent_id,
            visitor=_visitor_from_request(request),
            user_id=_require_user_id(_user),
        )
    )


@router.get(
    "/api/v1/course-agents/{agent_id}/sessions",
    response_model=ApiResponse[list[CourseAgentSessionSummaryDto]],
)
def list_agent_sessions(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(_agent_service(db, _user).list_sessions(agent_id, _require_user_id(_user)))


@router.get(
    "/api/v1/course-agent/sessions/{session_id}",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def get_agent_session(
    session_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(
        _agent_service(db, _user).get_session(parsed, user_id=_require_user_id(_user))
    )


@router.delete(
    "/api/v1/course-agent/sessions/{session_id}",
    response_model=ApiResponse[DeleteCourseAgentSessionResultDto],
)
def delete_agent_session(
    session_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    _agent_service(db, _user).delete_session(parsed, user_id=_require_user_id(_user))
    return success(DeleteCourseAgentSessionResultDto())


@router.post(
    "/api/v1/course-agent/sessions/{session_id}/messages",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def send_public_message(
    session_id: str,
    body: SendCourseAgentMessageBody,
    request: Request,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(
        _agent_service(db, _user).send_message(
            parsed,
            body.content,
            visitor=_visitor_from_request(request),
            user_id=_require_user_id(_user),
        )
    )


@router.post("/api/v1/course-agent/sessions/{session_id}/messages/stream")
def send_public_message_stream(
    session_id: str,
    body: SendCourseAgentMessageBody,
    request: Request,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    visitor = _visitor_from_request(request)
    user_id = _require_user_id(_user)
    service = _agent_service(db, _user)

    def event_stream():
        yield format_sse_event("ping", {"status": "started"})
        for event, data in service.iter_send_message_events(
            parsed, body.content, visitor=visitor, user_id=user_id
        ):
            yield format_sse_event(event, data if isinstance(data, dict) else {"data": data})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            **SSE_HEADERS,
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.post(
    "/api/v1/course-agent/sessions/{session_id}/reset",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def reset_public_session(
    session_id: str,
    request: Request,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(
        _agent_service(db, _user).reset_session(
            parsed,
            visitor=_visitor_from_request(request),
            user_id=_require_user_id(_user),
        )
    )
