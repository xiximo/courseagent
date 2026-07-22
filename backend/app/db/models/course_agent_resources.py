"""Course Agent 平台资源：知识库、模型配置（独立表）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CourseAgentKnowledgeBaseRecord(Base):
    """平台级知识库（与 Agent 解耦；Agent 通过 config 绑定 kb id）。"""

    __tablename__ = "course_agent_knowledge_base"
    __table_args__ = (
        UniqueConstraint("material_label", name="uq_cakb_material_label"),
        UniqueConstraint("standard_id", name="uq_cakb_standard"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # 遗留字段：历史数据可能仍有值；新库不再依赖 Agent
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    material_label: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    role: Mapped[str] = mapped_column(String(32), default="")
    standard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("standard.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(String(16), default="ready")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CourseAgentModelRecord(Base):
    """平台级模型配置（与 Agent 解耦；Agent 通过 config 绑定 model id）。"""

    __tablename__ = "course_agent_model"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(32), default="doubao")
    stream: Mapped[bool] = mapped_column(Boolean, default=False)
    model_name: Mapped[str] = mapped_column(String(128), default="")
    endpoint_id: Mapped[str] = mapped_column(String(128), default="")
    api_key: Mapped[str] = mapped_column(String(512), default="")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
