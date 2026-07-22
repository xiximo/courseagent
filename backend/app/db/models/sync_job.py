import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    partial = "partial"


class SyncTriggerType(str, enum.Enum):
    manual = "manual"
    scheduled = "scheduled"


class SyncMode(str, enum.Enum):
    full = "full"
    incremental = "incremental"


class SyncJob(Base):
    __tablename__ = "sync_job"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[SyncJobStatus] = mapped_column(
        Enum(SyncJobStatus, name="sync_job_status"),
        default=SyncJobStatus.pending,
        index=True,
    )
    trigger_type: Mapped[SyncTriggerType] = mapped_column(
        Enum(SyncTriggerType, name="sync_trigger_type"),
        default=SyncTriggerType.manual,
    )
    sync_mode: Mapped[SyncMode] = mapped_column(
        Enum(SyncMode, name="sync_mode"),
        default=SyncMode.incremental,
        index=True,
    )
    stand_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    page_current: Mapped[int] = mapped_column(Integer, default=0)
    page_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_size: Mapped[int] = mapped_column(Integer, default=10)
    start_page: Mapped[int] = mapped_column(Integer, default=1)
    max_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_page_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
