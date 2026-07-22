from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models.sprs_config import SprsConfigRecord


def get_or_create_sprs_config(db: Session) -> SprsConfigRecord:
    record = db.get(SprsConfigRecord, 1)
    if record is not None:
        return record

    env = get_settings()
    record = SprsConfigRecord(
        id=1,
        base_url=env.sprs_base_url,
        auth_type="token",
        auth_secret="",
        timeout_seconds=env.sprs_timeout_seconds,
        page_size=env.sprs_page_size,
        max_pages=env.sprs_max_pages,
        sync_cron="0 2 * * *",
        index_batch_size=200,
        default_stand_type=env.sprs_default_stand_type,
        download_attachments=env.sprs_download_attachments,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def mask_secret(secret: str) -> str:
    if not secret:
        return "（未配置）"
    if len(secret) <= 4:
        return "****"
    return f"{secret[:2]}****{secret[-2:]}"


def apply_env_fallback(record: SprsConfigRecord, env: Settings | None = None) -> SprsConfigRecord:
    """确保空字段回落到环境变量默认值。"""
    env = env or get_settings()
    if not record.base_url:
        record.base_url = env.sprs_base_url
    return record
