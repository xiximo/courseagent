from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.db.models.attachment import Attachment, AttachmentText, TextChunk
from app.db.models.standard import Standard
from app.db.models.sync_job import SyncJob
from app.db.models.sync_job_log import SyncJobLog
from app.storage import get_storage

STORAGE_PREFIX = "sprs/attachments/"


def purge_sync_database(db: Session) -> dict[str, int]:
    counts = {
        "sync_job_log": db.scalar(select(func.count()).select_from(SyncJobLog)) or 0,
        "sync_job": db.scalar(select(func.count()).select_from(SyncJob)) or 0,
        "text_chunk": db.scalar(select(func.count()).select_from(TextChunk)) or 0,
        "attachment_text": db.scalar(select(func.count()).select_from(AttachmentText)) or 0,
        "attachment": db.scalar(select(func.count()).select_from(Attachment)) or 0,
        "standard": db.scalar(select(func.count()).select_from(Standard)) or 0,
    }

    db.execute(update(Standard).values(last_sync_job_id=None, index_batch_id=None))
    db.execute(delete(TextChunk))
    db.execute(delete(AttachmentText))
    db.execute(delete(Attachment))
    db.execute(delete(Standard))
    db.execute(delete(SyncJobLog))
    db.execute(delete(SyncJob))
    db.commit()
    return counts


def purge_sync_storage() -> int:
    return get_storage().remove_prefix(STORAGE_PREFIX)


def purge_sync_minio() -> int:
    """兼容旧调用名。"""
    return purge_sync_storage()


def purge_all_sync_data(db: Session) -> tuple[dict[str, int], int]:
    counts = purge_sync_database(db)
    removed = purge_sync_storage()
    return counts, removed
