from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SprsConfigRecord(Base):
    """SPRS 同步运行时配置（单行，id=1）。"""

    __tablename__ = "sprs_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    base_url: Mapped[str] = mapped_column(String(512))
    auth_type: Mapped[str] = mapped_column(String(16), default="token")
    auth_secret: Mapped[str] = mapped_column(String(512), default="")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    page_size: Mapped[int] = mapped_column(Integer, default=10)
    max_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sync_cron: Mapped[str] = mapped_column(String(64), default="0 2 * * *")
    index_batch_size: Mapped[int] = mapped_column(Integer, default=200)
    default_stand_type: Mapped[str] = mapped_column(String(32), default="INLAND")
    download_attachments: Mapped[bool] = mapped_column(Boolean, default=True)
