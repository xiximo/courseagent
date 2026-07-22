from __future__ import annotations

import threading
import uuid

_running_attachments: set[uuid.UUID] = set()
_running_standards: set[uuid.UUID] = set()
_lock = threading.Lock()


def is_attachment_running(attachment_id: uuid.UUID) -> bool:
    with _lock:
        return attachment_id in _running_attachments


def is_standard_running(standard_id: uuid.UUID) -> bool:
    with _lock:
        return standard_id in _running_standards


def mark_attachment_running(attachment_id: uuid.UUID) -> bool:
    with _lock:
        if attachment_id in _running_attachments:
            return False
        _running_attachments.add(attachment_id)
        return True


def unmark_attachment_running(attachment_id: uuid.UUID) -> None:
    with _lock:
        _running_attachments.discard(attachment_id)


def mark_standard_running(standard_id: uuid.UUID) -> bool:
    with _lock:
        if standard_id in _running_standards:
            return False
        _running_standards.add(standard_id)
        return True


def unmark_standard_running(standard_id: uuid.UUID) -> None:
    with _lock:
        _running_standards.discard(standard_id)
