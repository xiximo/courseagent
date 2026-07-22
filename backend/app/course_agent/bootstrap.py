"""数据库初始化：建表 + 基础账号 / LLM 配置."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.course_agent.data_migration import migrate_all_agents_from_config_json
from app.db.base import Base
from app.db.models.user import AccountStatus, User
from app.db.session import SessionLocal, engine
from app.services.llm_settings import get_or_create_llm_config
from app.services.password import hash_password

logger = logging.getLogger(__name__)


def init_database() -> None:
    import app.db.models  # noqa: F401 — register all ORM models on Base

    Base.metadata.create_all(bind=engine)
    from app.course_agent.schema_patch import ensure_platform_resource_schema

    ensure_platform_resource_schema(engine)
    logger.info("Database tables ensured on %s", get_settings().database_url.split("@")[-1])

    with SessionLocal() as db:
        _ensure_admin_user(db)
        get_or_create_llm_config(db)
        migrate_all_agents_from_config_json(db)


def _ensure_admin_user(db: Session) -> None:
    settings = get_settings()
    username = settings.init_admin_username
    existing = db.scalar(select(User).where(User.username == username))
    if existing:
        return
    db.add(
        User(
            username=username,
            password_hash=hash_password(settings.init_admin_password),
            full_name="系统管理员",
            status=AccountStatus.enabled,
            role_codes=["sys_admin", "SYSTEM_ADMIN"],
        )
    )
    db.commit()
    logger.info("Default admin user created: %s", username)
