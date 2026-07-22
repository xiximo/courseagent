"""评审报告持久化。"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.db.models.review_report import ReviewReportRecord
from app.schemas.review_report import ReviewReportDto

logger = logging.getLogger(__name__)


class ReviewReportStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    def save(
        self,
        report: ReviewReportDto,
        *,
        created_by: str,
        created_by_user_id: uuid.UUID | None = None,
    ) -> ReviewReportDto:
        source_task_id = (report.sourceTaskId or report.taskId or "").strip()
        if not source_task_id:
            raise ApiBusinessError(
                "INVALID_REPORT",
                "报告缺少 sourceTaskId，无法持久化",
                400,
            )

        payload = report.model_dump(mode="json")
        existing = self.db.scalar(
            select(ReviewReportRecord).where(
                ReviewReportRecord.source_task_id == source_task_id
            )
        )

        if existing is not None:
            existing.report_json = payload
            existing.updated_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(existing)
            return ReviewReportDto.model_validate(existing.report_json)

        record_id = self._parse_report_id(report.taskId)
        record = ReviewReportRecord(
            id=record_id,
            source_task_id=source_task_id,
            report_json=payload,
            created_by=created_by or "system",
            created_by_user_id=created_by_user_id,
        )
        self.db.add(record)
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.exception("Failed to persist review report: %s", source_task_id)
            raise ApiBusinessError(
                "PERSIST_FAILED",
                f"评审报告保存失败：{exc}",
                500,
            ) from exc
        self.db.refresh(record)
        return ReviewReportDto.model_validate(record.report_json)

    def get_by_source_task_id(self, source_task_id: str) -> ReviewReportDto | None:
        record = self.db.scalar(
            select(ReviewReportRecord).where(
                ReviewReportRecord.source_task_id == source_task_id
            )
        )
        if record is None:
            return None
        return ReviewReportDto.model_validate(record.report_json)

    def get_by_id(self, report_id: str) -> ReviewReportDto | None:
        try:
            parsed_id = uuid.UUID(report_id)
        except ValueError:
            return None

        record = self.db.get(ReviewReportRecord, parsed_id)
        if record is None:
            return None
        return ReviewReportDto.model_validate(record.report_json)

    @staticmethod
    def _parse_report_id(task_id: str) -> uuid.UUID:
        try:
            return uuid.UUID(task_id)
        except ValueError:
            return uuid.uuid4()
