import uuid

from sqlalchemy.orm import Session

from app.db.models.sync_job_log import SyncJobLog, SyncLogLevel


def append_sync_log(
    db: Session,
    job_id: uuid.UUID,
    message: str,
    level: SyncLogLevel = SyncLogLevel.info,
) -> None:
    db.add(SyncJobLog(job_id=job_id, level=level, message=message))
    db.flush()
