from __future__ import annotations

import logging
import threading
import uuid

from app.db.session import SessionLocal
from app.sync.service import SyncService

logger = logging.getLogger(__name__)

_running_jobs: set[uuid.UUID] = set()
_lock = threading.Lock()


def enqueue_sync_job(job_id: uuid.UUID) -> None:
    with _lock:
        if job_id in _running_jobs:
            return
        _running_jobs.add(job_id)

    thread = threading.Thread(
        target=_execute_job,
        args=(job_id,),
        name=f"sync-job-{job_id}",
        daemon=True,
    )
    thread.start()


def _execute_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        SyncService(db).run_job(job_id)
    except Exception:
        logger.exception("Background sync job crashed: %s", job_id)
    finally:
        db.close()
        with _lock:
            _running_jobs.discard(job_id)
