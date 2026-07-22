from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HarnessPlatformConfigRecord(Base):
    """Harness 平台级配置（单行，id=1）：默认编排 + 模型路由。"""

    __tablename__ = "harness_platform_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    orchestration: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_routing: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
