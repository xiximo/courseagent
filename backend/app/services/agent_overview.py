from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.attachment import Attachment
from app.db.models.harness_skill import HarnessSkillRecord
from app.db.models.qa_session import QaMessageRecord, QaSessionRecord
from app.db.models.review_task import ReviewTask
from app.db.models.standard import Standard, StandardSyncStatus
from app.db.models.sync_job import SyncJob, SyncJobStatus
from app.schemas.agent import AgentOverviewDto, AgentOverviewKnowledgeStatsDto
from app.services.harness_platform_config import (
    get_or_create_harness_platform_config,
    to_model_routing_dto,
)
from app.services.llm_settings import get_or_create_llm_config, resolve_llm_runtime


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat().replace("+00:00", "Z")


def _today_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _resolve_sync_status(latest_job: SyncJob | None) -> str:
    if latest_job is None:
        return "stale"
    if latest_job.status == SyncJobStatus.running:
        return "syncing"
    if latest_job.status in {SyncJobStatus.completed, SyncJobStatus.partial}:
        return "healthy"
    return "stale"


class AgentOverviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def build_overview(self) -> AgentOverviewDto:
        now = datetime.now(UTC)
        today_start = _today_start()
        active_cutoff = now - timedelta(minutes=30)

        standard_count = self.db.scalar(select(func.count()).select_from(Standard)) or 0
        attachment_count = self.db.scalar(select(func.count()).select_from(Attachment)) or 0
        indexed_count = (
            self.db.scalar(
                select(func.count())
                .select_from(Standard)
                .where(Standard.sync_status == StandardSyncStatus.index_updated)
            )
            or 0
        )

        latest_job = self.db.scalar(
            select(SyncJob).order_by(SyncJob.created_at.desc()).limit(1)
        )

        sessions_today = (
            self.db.scalar(
                select(func.count())
                .select_from(QaSessionRecord)
                .where(QaSessionRecord.created_at >= today_start)
            )
            or 0
        )
        active_sessions = (
            self.db.scalar(
                select(func.count())
                .select_from(QaSessionRecord)
                .where(QaSessionRecord.updated_at >= active_cutoff)
            )
            or 0
        )
        qa_answers_today = (
            self.db.scalar(
                select(func.count())
                .select_from(QaMessageRecord)
                .where(
                    QaMessageRecord.role == "assistant",
                    QaMessageRecord.created_at >= today_start,
                )
            )
            or 0
        )
        review_tasks_today = (
            self.db.scalar(
                select(func.count())
                .select_from(ReviewTask)
                .where(ReviewTask.created_at >= today_start)
            )
            or 0
        )

        llm = resolve_llm_runtime(get_or_create_llm_config(self.db))
        harness = get_or_create_harness_platform_config(self.db)
        routing = to_model_routing_dto(harness)
        active_skills = (
            self.db.scalar(
                select(func.count())
                .select_from(HarnessSkillRecord)
                .where(HarnessSkillRecord.active_version != "")
            )
            or 0
        )

        batch_no = latest_job.batch_no if latest_job else "—"
        last_sync_at = (
            latest_job.finished_at
            or latest_job.updated_at
            or latest_job.created_at
            if latest_job
            else now
        )

        knowledge_stats = AgentOverviewKnowledgeStatsDto(
            batchNo=batch_no,
            standardCount=standard_count,
            attachmentCount=attachment_count,
            indexedCount=indexed_count,
            lastSyncAt=_iso(last_sync_at),
            syncStatus=_resolve_sync_status(latest_job),
        )

        return AgentOverviewDto(
            activeSessions=active_sessions,
            sessionsToday=sessions_today,
            toolCallsToday=qa_answers_today + review_tasks_today,
            qaAnswersToday=qa_answers_today,
            reviewTasksToday=review_tasks_today,
            avgLatencyMs=0,
            errorRateToday=0.0,
            citationGateBlockRate=0.0,
            modelVersion=llm.model_name or routing.defaultModel,
            knowledgeBaseBatch=batch_no,
            updatedAt=_iso(now),
            enabledProfiles=len(routing.profileOverrides),
            enabledTools=0,
            activeSkills=active_skills,
            knowledgeStats=knowledge_stats,
        )
