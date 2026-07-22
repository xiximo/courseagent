import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttachmentDownloadStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class AttachmentParseStatus(str, enum.Enum):
    pending = "pending"
    parsed = "parsed"
    failed = "failed"
    skipped = "skipped"


class Attachment(Base):
    __tablename__ = "attachment"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    standard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("standard.id", ondelete="CASCADE"), index=True
    )
    sprs_file_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    attr_field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_backend: Mapped[str] = mapped_column(String(32), default="minio")
    storage_bucket: Mapped[str] = mapped_column(String(128))
    storage_key: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    download_status: Mapped[AttachmentDownloadStatus] = mapped_column(
        Enum(AttachmentDownloadStatus, name="attachment_download_status"),
        default=AttachmentDownloadStatus.pending,
        index=True,
    )
    parse_status: Mapped[AttachmentParseStatus] = mapped_column(
        Enum(AttachmentParseStatus, name="attachment_parse_status"),
        default=AttachmentParseStatus.pending,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    standard: Mapped["Standard"] = relationship("Standard", back_populates="attachments")
    texts: Mapped[list["AttachmentText"]] = relationship(
        "AttachmentText", back_populates="attachment", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["TextChunk"]] = relationship(
        "TextChunk", back_populates="attachment", cascade="all, delete-orphan"
    )


class AttachmentText(Base):
    __tablename__ = "attachment_text"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachment.id", ondelete="CASCADE"), unique=True
    )
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    parse_engine: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parse_quality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    has_tables: Mapped[bool] = mapped_column(Boolean, default=False)
    has_figures: Mapped[bool] = mapped_column(Boolean, default=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    attachment: Mapped["Attachment"] = relationship("Attachment", back_populates="texts")


class TextChunk(Base):
    __tablename__ = "text_chunk"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachment.id", ondelete="CASCADE"), index=True
    )
    standard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("standard.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_type: Mapped[str] = mapped_column(String(32), default="clause", index=True)
    doc_role: Mapped[str] = mapped_column(String(32), default="body", index=True)
    content: Mapped[str] = mapped_column(Text)
    position_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clause_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    parent_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_caption: Mapped[str | None] = mapped_column(String(256), nullable=True)
    figure_caption: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    index_version: Mapped[int] = mapped_column(Integer, default=1)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    attachment: Mapped["Attachment"] = relationship("Attachment", back_populates="chunks")


if TYPE_CHECKING:
    from app.db.models.standard import Standard
