from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SyncJobStatusDto = Literal["pending", "running", "completed", "failed", "partial"]
SyncTriggerTypeDto = Literal["manual", "scheduled"]
SyncModeDto = Literal["full", "incremental"]


class TriggerSyncBody(BaseModel):
    mode: SyncModeDto = "incremental"
    standType: str | None = Field(default=None, description="INLAND / OUTLAND 等")
    triggerType: SyncTriggerTypeDto = "manual"
    pageSize: int | None = Field(default=None, ge=1, le=200)
    maxPages: int | None = Field(
        default=None,
        ge=0,
        le=9999,
        description="0 表示不限制；未传则使用系统配置；与 startPage 配合表示本批最多拉取页数",
    )
    startPage: int | None = Field(
        default=None,
        ge=1,
        le=9999,
        description="从第几页开始拉取，用于分批同步",
    )


class PurgeSyncDataResult(BaseModel):
    database: dict[str, int]
    minioObjectsRemoved: int


class SyncJobLogDto(BaseModel):
    id: str
    jobId: str
    level: Literal["info", "warn", "error"]
    message: str
    createdAt: str


class SyncJobDto(BaseModel):
    id: str
    batchNo: str
    status: SyncJobStatusDto
    triggerType: SyncTriggerTypeDto
    mode: SyncModeDto
    standType: str | None = None
    startPage: int = 1
    pageCurrent: int = 0
    pageTotal: int | None = None
    remotePageTotal: int | None = None
    startedAt: str | None = None
    finishedAt: str | None = None
    successCount: int = 0
    failedCount: int = 0
    failureReason: str | None = None


def to_sync_job_dto(job) -> SyncJobDto:
    return SyncJobDto(
        id=str(job.id),
        batchNo=job.batch_no,
        status=job.status.value,
        triggerType=job.trigger_type.value,
        mode=job.sync_mode.value,
        standType=job.stand_type,
        startPage=job.start_page or 1,
        pageCurrent=job.page_current,
        pageTotal=job.page_total,
        remotePageTotal=job.remote_page_total,
        startedAt=_iso(job.started_at),
        finishedAt=_iso(job.finished_at),
        successCount=job.success_count,
        failedCount=job.failed_count,
        failureReason=job.failure_reason,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
