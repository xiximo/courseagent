from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.session import get_db
from app.indexing.embedding_client import EmbeddingBackendError
from app.indexing.service import IndexingService
from app.processing.runner import enqueue_index, enqueue_index_all
from app.processing.service import ProcessingService
from app.processing.state import is_attachment_running, is_standard_running
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.indexing import ChunkSearchQuery, ChunkSearchResultDto
from app.schemas.processing import ProcessingActionResult

router = APIRouter(prefix="/api/v1/qibiao/indexing", tags=["qibiao-indexing"])


@router.post(
    "/attachments/{attachment_id}/index",
    response_model=ApiResponse[ProcessingActionResult],
)
def trigger_index_attachment(
    attachment_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "附件 ID 无效", 400) from exc

    service = ProcessingService(db)
    try:
        service._get_attachment(parsed_id)
    except ValueError as exc:
        raise ApiBusinessError("NOT_FOUND", str(exc), 404) from exc

    queued = enqueue_index(parsed_id)
    if not queued:
        raise ApiBusinessError("PROCESSING_BUSY", "该附件正在处理中", 409)

    return success(
        ProcessingActionResult(
            action="index",
            targetId=attachment_id,
            queued=1,
            message="向量索引任务已加入后台队列",
        )
    )


@router.post(
    "/standards/{standard_id}/index-all",
    response_model=ApiResponse[ProcessingActionResult],
)
def trigger_index_all(
    standard_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(standard_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "标准 ID 无效", 400) from exc

    if is_standard_running(parsed_id):
        raise ApiBusinessError("PROCESSING_BUSY", "该标准正在批量处理中", 409)

    service = ProcessingService(db)
    item = service.get_standard(parsed_id)
    if item is None:
        raise ApiBusinessError("NOT_FOUND", "标准不存在", 404)

    queued = enqueue_index_all(parsed_id)
    return success(
        ProcessingActionResult(
            action="index_all",
            targetId=standard_id,
            queued=1 if queued else 0,
            message="批量向量索引任务已启动",
        )
    )


@router.post(
    "/search/chunks",
    response_model=ApiResponse[ChunkSearchResultDto],
)
def search_chunks(
    body: ChunkSearchQuery,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    standard_id = _parse_optional_uuid(body.standardId, "标准 ID 无效")
    attachment_id = _parse_optional_uuid(body.attachmentId, "附件 ID 无效")

    service = IndexingService(db)
    try:
        if body.mode == "keyword":
            hits = service.keyword_search_chunks(
                body.query,
                standard_id=standard_id,
                attachment_id=attachment_id,
                chunk_type=body.chunkType,
                doc_role=body.docRole,
                top_k=body.topK,
            )
            result = ChunkSearchResultDto(
                query=body.query.strip(),
                mode="keyword",
                hits=hits,
            )
        elif body.mode == "semantic":
            result = service.semantic_search_chunks(
                body.query,
                standard_id=standard_id,
                attachment_id=attachment_id,
                chunk_type=body.chunkType,
                doc_role=body.docRole,
                top_k=body.topK,
            )
        else:
            result = service.hybrid_search_chunks(
                body.query,
                standard_id=standard_id,
                attachment_id=attachment_id,
                chunk_type=body.chunkType,
                doc_role=body.docRole,
                top_k=body.topK,
            )
    except EmbeddingBackendError as exc:
        raise ApiBusinessError("EMBEDDING_BACKEND_ERROR", str(exc), 503) from exc

    return success(result)


def _parse_optional_uuid(value: str | None, message: str) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", message, 400) from exc
