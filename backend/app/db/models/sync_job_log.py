import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncLogLevel(str, enum.Enum):
    info = "info"
    warn = "warn"
    error = "error"


class SyncJobLog(Base):
    __tablename__ = "sync_job_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_job.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[SyncLogLevel] = mapped_column(
        Enum(SyncLogLevel, name="sync_log_level"), default=SyncLogLevel.info
    )
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
