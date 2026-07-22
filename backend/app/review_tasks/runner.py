from __future__ import annotations

import logging
import threading
import uuid

from app.db.session import SessionLocal
from app.review_tasks.service import ReviewTaskService

logger = logging.getLogger(__name__)

_running_tasks: set[uuid.UUID] = set()
_lock = threading.Lock()


def enqueue_review_task(task_id: uuid.UUID) -> None:
    with _lock:
        if task_id in _running_tasks:
            return
        _running_tasks.add(task_id)

    thread = threading.Thread(
        target=_execute_task,
        args=(task_id,),
        name=f"review-task-{task_id}",
        daemon=True,
    )
    thread.start()


def _execute_task(task_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        ReviewTaskService(db).run_task(task_id)
    except Exception:
        logger.exception("Background review task crashed: %s", task_id)
    finally:
        db.close()
        with _lock:
            _running_tasks.discard(task_id)
