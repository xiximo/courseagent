import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.session import get_db
from app.processing.runner import (
    enqueue_chunk,
    enqueue_chunk_all,
    enqueue_extract_all,
    enqueue_extract_text,
)
from app.processing.state import is_attachment_running, is_standard_running
from app.processing.service import ProcessingService
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.processing import (
    AttachmentChunksDto,
    AttachmentExtractedTextDto,
    ProcessingActionResult,
    ProcessingPageResult,
    StandardProcessingDto,
)

router = APIRouter(prefix="/api/v1/qibiao/processing", tags=["qibiao-processing"])


@router.get("/standards", response_model=ApiResponse[ProcessingPageResult])
def list_processing_standards(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    standardNo: str | None = Query(default=None),
    name: str | None = Query(default=None),
    syncStatus: str | None = Query(default=None),
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ProcessingService(db)
    result = service.list_standards(
        page=page,
        page_size=pageSize,
        standard_no=standardNo,
        name=name,
        sync_status=syncStatus,
        include_attachments=True,
    )
    return success(result)


@router.get(
    "/standards/{standard_id}",
    response_model=ApiResponse[StandardProcessingDto],
)
def get_processing_standard(
    standard_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(standard_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "标准 ID 无效", 400) from exc

    service = ProcessingService(db)
    item = service.get_standard(parsed_id)
    if item is None:
        raise ApiBusinessError("NOT_FOUND", "标准不存在", 404)
    return success(item)


@router.post(
    "/attachments/{attachment_id}/extract-text",
    response_model=ApiResponse[ProcessingActionResult],
)
def trigger_extract_text(
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

    queued = enqueue_extract_text(parsed_id)
    if not queued:
        raise ApiBusinessError("PROCESSING_BUSY", "该附件正在处理中", 409)

    return success(
        ProcessingActionResult(
            action="extract_text",
            targetId=attachment_id,
            queued=1,
            message="文本抽取任务已加入后台队列",
        )
    )


@router.post(
    "/attachments/{attachment_id}/chunk",
    response_model=ApiResponse[ProcessingActionResult],
)
def trigger_chunk(
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

    queued = enqueue_chunk(parsed_id)
    if not queued:
        raise ApiBusinessError("PROCESSING_BUSY", "该附件正在处理中", 409)

    return success(
        ProcessingActionResult(
            action="chunk",
            targetId=attachment_id,
            queued=1,
            message="结构切片任务已加入后台队列",
        )
    )


@router.post(
    "/standards/{standard_id}/extract-all",
    response_model=ApiResponse[ProcessingActionResult],
)
def trigger_extract_all(
    standard_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(standard_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "标准 ID 无效", 400) from exc

    service = ProcessingService(db)
    item = service.get_standard(parsed_id)
    if item is None:
        raise ApiBusinessError("NOT_FOUND", "标准不存在", 404)

    if is_standard_running(parsed_id):
        raise ApiBusinessError("PROCESSING_BUSY", "该标准正在批量处理中", 409)

    queued = enqueue_extract_all(parsed_id)
    return success(
        ProcessingActionResult(
            action="extract_all",
            targetId=standard_id,
            queued=1 if queued else 0,
            message="批量文本抽取任务已启动",
        )
    )


@router.post(
    "/standards/{standard_id}/chunk-all",
    response_model=ApiResponse[ProcessingActionResult],
)
def trigger_chunk_all(
    standard_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(standard_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "标准 ID 无效", 400) from exc

    service = ProcessingService(db)
    item = service.get_standard(parsed_id)
    if item is None:
        raise ApiBusinessError("NOT_FOUND", "标准不存在", 404)

    if is_standard_running(parsed_id):
        raise ApiBusinessError("PROCESSING_BUSY", "该标准正在批量处理中", 409)

    queued = enqueue_chunk_all(parsed_id)
    return success(
        ProcessingActionResult(
            action="chunk_all",
            targetId=standard_id,
            queued=1 if queued else 0,
            message="批量结构切片任务已启动",
        )
    )


@router.get(
    "/attachments/{attachment_id}/extracted-text",
    response_model=ApiResponse[AttachmentExtractedTextDto],
)
def get_attachment_extracted_text(
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

    result = service.get_extracted_text(parsed_id)
    if result is None:
        raise ApiBusinessError("TEXT_NOT_FOUND", "附件尚未完成文本抽取", 404)
    return success(result)


@router.get(
    "/attachments/{attachment_id}/chunks",
    response_model=ApiResponse[AttachmentChunksDto],
)
def get_attachment_chunks(
    attachment_id: str,
    chunkType: str | None = Query(default=None, alias="chunkType"),
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

    result = service.get_attachment_chunks(parsed_id, chunk_type=chunkType)
    if result is None:
        raise ApiBusinessError("CHUNKS_NOT_FOUND", "附件尚未完成结构切片", 404)
    return success(result)


@router.get("/attachments/{attachment_id}/extracted-assets/{asset_name}")
def get_attachment_extracted_asset(
    attachment_id: str,
    asset_name: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "附件 ID 无效", 400) from exc

    service = ProcessingService(db)
    try:
        payload, content_type = service.get_extracted_asset_bytes(parsed_id, asset_name)
    except ValueError as exc:
        message = str(exc)
        code = "NOT_FOUND" if "不存在" in message else "INVALID_ASSET"
        status = 404 if code == "NOT_FOUND" else 400
        raise ApiBusinessError(code, message, status) from exc

    return Response(content=payload, media_type=content_type)


@router.post(
    "/attachments/{attachment_id}/redownload",
    response_model=ApiResponse[ProcessingActionResult],
)
def trigger_redownload_attachment(
    attachment_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "附件 ID 无效", 400) from exc

    if is_attachment_running(parsed_id):
        raise ApiBusinessError("PROCESSING_BUSY", "该附件正在处理中", 409)

    service = ProcessingService(db)
    try:
        service.redownload_attachment(parsed_id)
    except ValueError as exc:
        message = str(exc)
        if "不存在" in message:
            raise ApiBusinessError("NOT_FOUND", message, 404) from exc
        if "正在处理中" in message:
            raise ApiBusinessError("PROCESSING_BUSY", message, 409) from exc
        raise ApiBusinessError("REDOWNLOAD_FAILED", message, 400) from exc

    return success(
        ProcessingActionResult(
            action="redownload",
            targetId=attachment_id,
            queued=0,
            message="附件已从 SPRS 重新下载并覆盖本地副本",
        )
    )


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
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
        payload, file_name, content_type = service.get_attachment_bytes(parsed_id)
    except ValueError as exc:
        raise ApiBusinessError("ATTACHMENT_NOT_READY", str(exc), 400) from exc

    # Starlette 响应头须 latin-1；中文文件名用 RFC 5987 filename*（与 FileResponse 一致）
    quoted = quote(file_name)
    if quoted != file_name:
        disposition = f"inline; filename*=utf-8''{quoted}"
    else:
        disposition = f'inline; filename="{file_name}"'
    headers = {"Content-Disposition": disposition}
    return Response(content=payload, media_type=content_type, headers=headers)
