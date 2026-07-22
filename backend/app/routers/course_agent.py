from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.course_agent.material_service import MaterialService
from app.course_agent.model_service import ModelService
from app.course_agent.service import CourseAgentService
from app.db.session import get_db
from app.review.sse import format_sse_event
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.course_agent import (
    CourseAgentConfigDto,
    CourseAgentKnowledgeBaseDto,
    CourseAgentLeadDetailDto,
    CourseAgentLeadSummaryDto,
    CourseAgentModelProfileDto,
    CourseAgentPatchBody,
    CourseAgentSessionDto,
    CourseAgentSummaryDto,
    CourseMaterialActionResultDto,
    CourseMaterialDocumentDto,
    CreateCourseAgentBody,
    CreateCourseKnowledgeBaseBody,
    CreateCourseModelBody,
    DeleteCourseAgentLeadResultDto,
    DeleteCourseAgentResultDto,
    DeleteCourseKnowledgeBaseResultDto,
    DeleteCourseModelResultDto,
    PublicAgentConfigDto,
    SendCourseAgentMessageBody,
    UpdateCourseKnowledgeBaseBody,
    UpdateCourseModelBody,
)
from app.schemas.processing import AttachmentExtractedTextDto

router = APIRouter(tags=["course-agent"])

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


def _optional_embed_verify(
    request: Request,
    agent_id: str,
    embed_key: Annotated[str | None, Header(alias="X-Embed-Key")] = None,
    db: Session = Depends(get_db),
) -> None:
    CourseAgentService(db).verify_embed_access(
        agent_id, embed_key, _origin_from_request(request)
    )


# --- 管理端（需 JWT）---


@router.get("/api/v1/course-agents", response_model=ApiResponse[list[CourseAgentSummaryDto]])
def list_course_agents(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(CourseAgentService(db).list_agents())


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
        CourseAgentService(db).list_leads(
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
    return success(CourseAgentService(db).get_lead(parsed))


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
        DeleteCourseAgentLeadResultDto(**CourseAgentService(db).delete_lead(parsed))
    )


@router.post(
    "/api/v1/course-agents",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def create_course_agent(
    body: CreateCourseAgentBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(CourseAgentService(db).create_agent(body))


@router.delete(
    "/api/v1/course-agents/{agent_id}",
    response_model=ApiResponse[DeleteCourseAgentResultDto],
)
def delete_course_agent(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(DeleteCourseAgentResultDto(**CourseAgentService(db).delete_agent(agent_id)))


@router.get(
    "/api/v1/course-agents/{agent_id}",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def get_course_agent(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(CourseAgentService(db).get_agent(agent_id))


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
    return success(CourseAgentService(db).update_agent(agent_id, body))


@router.post(
    "/api/v1/course-agents/{agent_id}/set-default",
    response_model=ApiResponse[CourseAgentConfigDto],
)
def set_default_course_agent(
    agent_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(CourseAgentService(db).set_default_agent(agent_id))


@router.get(
    "/api/v1/platform/knowledge-bases",
    response_model=ApiResponse[list[CourseAgentKnowledgeBaseDto]],
)
def list_platform_knowledge_bases(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(MaterialService(db).list_all_knowledge_bases())


@router.post(
    "/api/v1/platform/knowledge-bases",
    response_model=ApiResponse[CourseAgentKnowledgeBaseDto],
)
def create_platform_knowledge_base(
    body: CreateCourseKnowledgeBaseBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(
        MaterialService(db).create_knowledge_base(
            name=body.name,
            description=body.description,
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
    return success(MaterialService(db).get_knowledge_base(kb_id))


@router.patch(
    "/api/v1/platform/knowledge-bases/{kb_id}",
    response_model=ApiResponse[CourseAgentKnowledgeBaseDto],
)
def update_platform_knowledge_base(
    kb_id: str,
    body: UpdateCourseKnowledgeBaseBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success(
        MaterialService(db).update_knowledge_base(
            kb_id,
            name=body.name,
            description=body.description,
        )
    )


@router.delete(
    "/api/v1/platform/knowledge-bases/{kb_id}",
    response_model=ApiResponse[DeleteCourseKnowledgeBaseResultDto],
)
def delete_platform_knowledge_base(
    kb_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    MaterialService(db).delete_knowledge_base(kb_id)
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
    material = MaterialService(db)
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
    _user: AuthUserProfile = Depends(get_current_user),
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
    material = MaterialService(db)
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
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(attachment_id, label="文档 ID")
    material = MaterialService(db)
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
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material = MaterialService(db)
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
    kb = MaterialService(db).create_knowledge_base(
        name=body.name,
        description=body.description,
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
    kb = MaterialService(db).update_knowledge_base(
        kb_id,
        name=body.name,
        description=body.description,
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
    MaterialService(db).delete_knowledge_base(kb_id)
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
    docs = MaterialService(db).list_material_documents(material_label)
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

    kb = MaterialService(db).upload_material(
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
    kb = MaterialService(db).delete_material_document(material_label, parsed)
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
    kb = MaterialService(db).reindex_material(material_label)
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
    return success(CourseAgentService(db).create_preview_session(agent_id))


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
    return success(CourseAgentService(db).send_preview_message(parsed, body.content))


@router.post("/api/v1/course-agent/preview/sessions/{session_id}/messages/stream")
def send_preview_message_stream(
    session_id: str,
    body: SendCourseAgentMessageBody,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    service = CourseAgentService(db)

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
    return success(CourseAgentService(db).reset_preview_session(parsed))


# --- 公开 API（无 JWT）---


@router.get(
    "/api/v1/course-agents/{agent_id}/public-config",
    response_model=ApiResponse[PublicAgentConfigDto],
)
def get_public_agent_config(agent_id: str, db: Session = Depends(get_db)):
    return success(CourseAgentService(db).get_public_config(agent_id))


@router.get(
    "/api/v1/course-agent/attachments/{attachment_id}/extracted-text",
    response_model=ApiResponse[AttachmentExtractedTextDto],
)
def get_public_attachment_extracted_text(
    attachment_id: str,
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(attachment_id, label="附件 ID")
    return success(CourseAgentService(db).get_public_attachment_extracted_text(parsed))


@router.post(
    "/api/v1/course-agents/{agent_id}/sessions",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def create_public_session(
    agent_id: str,
    request: Request,
    embed_key: Annotated[str | None, Header(alias="X-Embed-Key")] = None,
    db: Session = Depends(get_db),
):
    CourseAgentService(db).verify_embed_access(
        agent_id, embed_key, _origin_from_request(request)
    )
    return success(
        CourseAgentService(db).create_session(
            agent_id, visitor=_visitor_from_request(request)
        )
    )


@router.post(
    "/api/v1/course-agent/sessions/{session_id}/messages",
    response_model=ApiResponse[CourseAgentSessionDto],
)
def send_public_message(
    session_id: str,
    body: SendCourseAgentMessageBody,
    request: Request,
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(
        CourseAgentService(db).send_message(
            parsed, body.content, visitor=_visitor_from_request(request)
        )
    )


@router.post("/api/v1/course-agent/sessions/{session_id}/messages/stream")
def send_public_message_stream(
    session_id: str,
    body: SendCourseAgentMessageBody,
    request: Request,
    db: Session = Depends(get_db),
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    visitor = _visitor_from_request(request)
    service = CourseAgentService(db)

    def event_stream():
        yield format_sse_event("ping", {"status": "started"})
        for event, data in service.iter_send_message_events(
            parsed, body.content, visitor=visitor
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
    session_id: str, request: Request, db: Session = Depends(get_db)
):
    parsed = _parse_uuid(session_id, label="会话 ID")
    return success(
        CourseAgentService(db).reset_session(
            parsed, visitor=_visitor_from_request(request)
        )
    )
