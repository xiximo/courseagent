from __future__ import annotations

import logging
import threading
import uuid

from app.db.session import SessionLocal
from app.processing.service import ProcessingService
from app.processing.state import (
    mark_attachment_running,
    mark_standard_running,
    unmark_attachment_running,
    unmark_standard_running,
)

logger = logging.getLogger(__name__)


def enqueue_extract_text(attachment_id: uuid.UUID) -> bool:
    return _enqueue_attachment(attachment_id, "extract")


def enqueue_chunk(attachment_id: uuid.UUID) -> bool:
    return _enqueue_attachment(attachment_id, "chunk")


def enqueue_index(attachment_id: uuid.UUID) -> bool:
    return _enqueue_attachment(attachment_id, "index")


def enqueue_index_all(standard_id: uuid.UUID) -> bool:
    if not mark_standard_running(standard_id):
        return False

    thread = threading.Thread(
        target=_execute_standard,
        args=(standard_id, "index_all"),
        name=f"processing-index-all-{standard_id}",
        daemon=True,
    )
    thread.start()
    return True


def enqueue_extract_all(standard_id: uuid.UUID) -> bool:
    if not mark_standard_running(standard_id):
        return False

    thread = threading.Thread(
        target=_execute_standard,
        args=(standard_id, "extract_all"),
        name=f"processing-extract-all-{standard_id}",
        daemon=True,
    )
    thread.start()
    return True


def enqueue_chunk_all(standard_id: uuid.UUID) -> bool:
    if not mark_standard_running(standard_id):
        return False

    thread = threading.Thread(
        target=_execute_standard,
        args=(standard_id, "chunk_all"),
        name=f"processing-chunk-all-{standard_id}",
        daemon=True,
    )
    thread.start()
    return True


def _enqueue_attachment(attachment_id: uuid.UUID, action: str) -> bool:
    if not mark_attachment_running(attachment_id):
        return False

    thread = threading.Thread(
        target=_execute_attachment,
        args=(attachment_id, action),
        name=f"processing-{action}-{attachment_id}",
        daemon=True,
    )
    thread.start()
    return True


def _execute_attachment(attachment_id: uuid.UUID, action: str) -> None:
    db = SessionLocal()
    try:
        service = ProcessingService(db)
        if action == "extract":
            service.extract_text(attachment_id)
        elif action == "chunk":
            service.chunk_attachment(attachment_id)
        elif action == "index":
            from app.indexing.service import IndexingService

            IndexingService(db).index_attachment(attachment_id)
    except Exception:
        logger.exception("Attachment processing failed: %s (%s)", attachment_id, action)
    finally:
        db.close()
        unmark_attachment_running(attachment_id)


def _execute_standard(standard_id: uuid.UUID, action: str) -> None:
    db = SessionLocal()
    try:
        service = ProcessingService(db)
        if action == "extract_all":
            service.extract_all_for_standard(standard_id)
        elif action == "chunk_all":
            service.chunk_all_for_standard(standard_id)
        elif action == "index_all":
            from app.indexing.service import IndexingService

            IndexingService(db).index_all_for_standard(standard_id)
    except Exception:
        logger.exception("Standard processing failed: %s (%s)", standard_id, action)
    finally:
        db.close()
        unmark_standard_running(standard_id)
