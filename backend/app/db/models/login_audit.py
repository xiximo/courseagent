import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginAuditLog(Base):
    __tablename__ = "login_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(64), index=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    logged_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
