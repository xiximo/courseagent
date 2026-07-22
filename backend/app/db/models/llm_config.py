from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LlmConfigRecord(Base):
    """LLM 问答运行时配置（单行，id=1）。"""

    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    provider: Mapped[str] = mapped_column(String(32), default="doubao")
    model_name: Mapped[str] = mapped_column(String(128), default="")
    endpoint_id: Mapped[str] = mapped_column(String(128), default="")
    api_key: Mapped[str] = mapped_column(String(512), default="")
    base_url: Mapped[str] = mapped_column(
        String(512), default="https://ark.cn-beijing.volces.com/api/v3"
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    qa_top_k: Mapped[int] = mapped_column(Integer, default=8)
