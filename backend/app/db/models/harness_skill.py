from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class HarnessSkillRecord(Base):
    """Harness Skill 元数据（正文暂存 DB，后续可迁 Git）。"""

    __tablename__ = "harness_skill"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    active_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    versions: Mapped[list["HarnessSkillVersionRecord"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="HarnessSkillVersionRecord.deployed_at.desc()",
    )


class HarnessSkillVersionRecord(Base):
    __tablename__ = "harness_skill_version"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_harness_skill_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    skill_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("harness_skill.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    changelog: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    skill: Mapped[HarnessSkillRecord] = relationship(back_populates="versions")
