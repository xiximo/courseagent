import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StandardSyncStatus(str, enum.Enum):
    not_synced = "not_synced"
    synced = "synced"
    attachment_downloaded = "attachment_downloaded"
    text_parsed = "text_parsed"
    index_updated = "index_updated"
    sync_failed = "sync_failed"


class Standard(Base):
    __tablename__ = "standard"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sprs_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    stand_type: Mapped[str] = mapped_column(String(32), index=True)
    stand_sort: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stand_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stand_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    standard_no: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    english_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stand_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stand_state_show: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stand_nature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text_status_show: Mapped[str | None] = mapped_column(String(64), nullable=True)
    part_code: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    part_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    publish_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_flag: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sprs_modify_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_status: Mapped[StandardSyncStatus] = mapped_column(
        Enum(StandardSyncStatus, name="standard_sync_status"),
        default=StandardSyncStatus.not_synced,
        index=True,
    )
    attr_info_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    attr_info_case_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    index_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("index_batch.id"), nullable=True
    )
    last_sync_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sync_job.id"), nullable=True
    )
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="standard", cascade="all, delete-orphan"
    )


if TYPE_CHECKING:
    from app.db.models.attachment import Attachment
