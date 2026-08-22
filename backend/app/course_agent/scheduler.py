"""进程内轮询：检查到期的 Harness 定时任务。"""

from __future__ import annotations

import asyncio
import logging
import threading

from app.config import get_settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_run_lock = threading.Lock()


def _tick_once() -> None:
    from app.course_agent.schedule import run_due_harness_jobs

    if not _run_lock.acquire(blocking=False):
        logger.info("Harness scheduler skipped overlapping tick")
        return
    db = SessionLocal()
    try:
        ran = run_due_harness_jobs(db)
        if ran:
            logger.info("Harness scheduler ran %s job(s)", ran)
    except Exception:
        logger.exception("Harness scheduler tick failed")
        db.rollback()
    finally:
        db.close()
        _run_lock.release()


async def harness_scheduler_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    poll = max(10, int(settings.harness_scheduler_poll_seconds or 30))
    await asyncio.sleep(min(20, poll))
    while not stop.is_set():
        try:
            await asyncio.to_thread(_tick_once)
        except Exception:
            logger.exception("Harness scheduler loop error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll)
        except TimeoutError:
            continue
