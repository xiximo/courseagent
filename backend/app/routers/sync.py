import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.models.sync_job import SyncJob, SyncJobStatus, SyncMode, SyncTriggerType
from app.db.models.sync_job_log import SyncJobLog
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.sync import (
    PurgeSyncDataResult,
    SyncJobDto,
    SyncJobLogDto,
    TriggerSyncBody,
    to_sync_job_dto,
)
from app.services.purge_sync import purge_all_sync_data
from app.sync.runner import enqueue_sync_job
from app.sync.service import SyncService

router = APIRouter(prefix="/api/v1/qibiao/sync", tags=["qibiao-sync"])


@router.get("/jobs", response_model=ApiResponse[list[SyncJobDto]])
def list_sync_jobs(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    jobs = db.scalars(select(SyncJob).order_by(SyncJob.created_at.desc()).limit(50)).all()
    return success([to_sync_job_dto(job) for job in jobs])


@router.post("/jobs", response_model=ApiResponse[SyncJobDto])
def trigger_sync(
    body: TriggerSyncBody | None = None,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = body or TriggerSyncBody()
    service = SyncService(db)
    job = service.create_job(
        sync_mode=SyncMode(payload.mode),
        stand_type=payload.standType,
        trigger_type=SyncTriggerType(payload.triggerType),
        page_size=payload.pageSize,
        max_pages=payload.maxPages,
        start_page=payload.startPage,
    )
    enqueue_sync_job(job.id)
    return success(to_sync_job_dto(job))


@router.post("/jobs/{job_id}/retry", response_model=ApiResponse[SyncJobDto])
def retry_sync_job(
    job_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "任务 ID 无效", 400) from exc

    service = SyncService(db)
    try:
        job = service.retry_job(parsed_id)
    except ValueError as exc:
        raise ApiBusinessError("SYNC_RETRY_FAILED", str(exc), 400) from exc

    enqueue_sync_job(job.id)
    return success(to_sync_job_dto(job))


@router.get("/jobs/{job_id}/logs", response_model=ApiResponse[list[SyncJobLogDto]])
def list_sync_job_logs(
    job_id: str,
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "任务 ID 无效", 400) from exc

    job = db.get(SyncJob, parsed_id)
    if not job:
        raise ApiBusinessError("NOT_FOUND", "同步任务不存在", 404)

    logs = db.scalars(
        select(SyncJobLog)
        .where(SyncJobLog.job_id == parsed_id)
        .order_by(SyncJobLog.created_at.desc())
        .limit(2000)
    ).all()
    logs.reverse()

    return success(
        [
            SyncJobLogDto(
                id=str(log.id),
                jobId=str(log.job_id),
                level=log.level.value,
                message=log.message,
                createdAt=log.created_at.isoformat(),
            )
            for log in logs
        ]
    )


@router.post("/purge", response_model=ApiResponse[PurgeSyncDataResult])
def purge_sync_data(
    _user: AuthUserProfile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    running = db.scalar(
        select(SyncJob.id)
        .where(
            SyncJob.status.in_([SyncJobStatus.pending, SyncJobStatus.running])
        )
        .limit(1)
    )
    if running:
        raise ApiBusinessError(
            "SYNC_RUNNING",
            "存在进行中的同步任务，请等待完成后再清理",
            409,
        )

    counts, removed = purge_all_sync_data(db)
    return success(
        PurgeSyncDataResult(database=counts, minioObjectsRemoved=removed)
    )
