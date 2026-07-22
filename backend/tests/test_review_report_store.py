"""Review report persistence unit tests."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from unittest.mock import MagicMock

from app.db.models.review_report import ReviewReportRecord
from app.review.report_store import ReviewReportStore
from app.schemas.review_report import ReviewReportDto


def _sample_report() -> ReviewReportDto:
    return ReviewReportDto(
        taskId="11111111-1111-1111-1111-111111111111",
        sourceTaskId="22222222-2222-2222-2222-222222222222",
        finalConclusion="建议修订。",
        generatedAt="2026-07-10T00:00:00+00:00",
    )


def test_save_creates_record() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    store = ReviewReportStore(db)
    report = store.save(_sample_report(), created_by="admin")

    db.add.assert_called_once()
    db.commit.assert_called_once()
    assert report.sourceTaskId == "22222222-2222-2222-2222-222222222222"
    added = db.add.call_args.args[0]
    assert isinstance(added, ReviewReportRecord)
    assert added.created_by == "admin"


def test_save_updates_existing_by_source_task_id() -> None:
    db = MagicMock()
    existing = ReviewReportRecord(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        source_task_id="22222222-2222-2222-2222-222222222222",
        report_json={"taskId": "old"},
        created_by="admin",
    )
    db.scalar.return_value = existing
    store = ReviewReportStore(db)

    updated = _sample_report()
    updated.finalConclusion = "更新后的结论"
    report = store.save(updated, created_by="admin")

    db.add.assert_not_called()
    db.commit.assert_called_once()
    assert existing.report_json["finalConclusion"] == "更新后的结论"
    assert report.finalConclusion == "更新后的结论"


def test_save_uses_task_id_when_source_task_id_missing() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    store = ReviewReportStore(db)
    task_id = str(uuid.uuid4())
    report = ReviewReportDto(taskId=task_id, sourceTaskId="", finalConclusion="x")

    store.save(report, created_by="admin")

    added = db.add.call_args.args[0]
    assert added.source_task_id == task_id
