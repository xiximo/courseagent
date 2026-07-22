import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CourseAgentRecord(Base):
    __tablename__ = "course_agent"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["CourseAgentSessionRecord"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class CourseAgentSessionRecord(Base):
    __tablename__ = "course_agent_session"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("course_agent.agent_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(256), default="新对话")
    step: Mapped[str] = mapped_column(String(32), default="welcome")
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    constraints_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    recommended_courses: Mapped[list] = mapped_column(JSONB, default=list)
    locked_course: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent: Mapped[CourseAgentRecord] = relationship(back_populates="sessions")
    messages: Mapped[list["CourseAgentMessageRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CourseAgentMessageRecord.created_at",
    )
    leads: Mapped[list["CourseAgentLeadRecord"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CourseAgentLeadRecord.consultation_index",
    )


class CourseAgentLeadRecord(Base):
    """一次客户咨询线索：同一浏览器会话内每次「重新开始」开启新线索。"""

    __tablename__ = "course_agent_lead"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("course_agent.agent_id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_agent_session.id", ondelete="CASCADE"),
        index=True,
    )
    consultation_index: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str | None] = mapped_column(String(512), nullable=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    title: Mapped[str] = mapped_column(String(256), default="客户咨询")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    session: Mapped[CourseAgentSessionRecord] = relationship(back_populates="leads")
    messages: Mapped[list["CourseAgentMessageRecord"]] = relationship(
        back_populates="lead",
        order_by="CourseAgentMessageRecord.created_at",
    )


class CourseAgentMessageRecord(Base):
    __tablename__ = "course_agent_message"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_agent_session.id", ondelete="CASCADE"),
        index=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_agent_lead.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    citations_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    quick_actions_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[CourseAgentSessionRecord] = relationship(back_populates="messages")
    lead: Mapped[CourseAgentLeadRecord | None] = relationship(back_populates="messages")
