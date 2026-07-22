"""客户咨询线索：同一会话内每次「重新开始」开启新线索。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.errors import ApiBusinessError
from app.course_agent.rag import enrich_citations_with_attachments
from app.course_agent.state_machine import Citation
from app.db.models.course_agent import (
    CourseAgentLeadRecord,
    CourseAgentMessageRecord,
    CourseAgentRecord,
    CourseAgentSessionRecord,
)
from app.schemas.course_agent import (
    CourseAgentLeadDetailDto,
    CourseAgentLeadSummaryDto,
    CourseAgentMessageDto,
)


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(UTC).isoformat()
    return dt.isoformat()


@dataclass(frozen=True)
class VisitorContext:
    client_ip: str | None = None
    user_agent: str | None = None
    origin: str | None = None


RESTART_TEXTS = frozenset({"重新开始", "重来", "取消", "重置", "reset", "restart"})


def is_restart_text(content: str) -> bool:
    return content.strip() in RESTART_TEXTS


def build_profile_snapshot(session: CourseAgentSessionRecord) -> dict[str, Any]:
    raw = dict(session.constraints_json or {})
    constraints = {
        key: raw.get(key)
        for key in ("city", "date", "format", "goal", "budget")
        if raw.get(key) not in (None, "")
    }
    return {
        "role": session.role,
        "constraints": constraints,
        "recommendedCourses": list(session.recommended_courses or []),
        "lockedCourse": session.locked_course,
        "step": session.step,
    }


class CourseAgentLeadService:
    def __init__(self, db: Session):
        self.db = db

    def get_open_lead(
        self, session_id: uuid.UUID
    ) -> CourseAgentLeadRecord | None:
        return self.db.scalar(
            select(CourseAgentLeadRecord)
            .where(
                CourseAgentLeadRecord.session_id == session_id,
                CourseAgentLeadRecord.status == "open",
            )
            .order_by(CourseAgentLeadRecord.consultation_index.desc())
        )

    def open_lead(
        self,
        session: CourseAgentSessionRecord,
        visitor: VisitorContext | None = None,
        *,
        inherit_from: CourseAgentLeadRecord | None = None,
    ) -> CourseAgentLeadRecord:
        max_idx = self.db.scalar(
            select(func.max(CourseAgentLeadRecord.consultation_index)).where(
                CourseAgentLeadRecord.session_id == session.id
            )
        )
        index = int(max_idx or 0) + 1
        visitor = visitor or VisitorContext()
        ip = visitor.client_ip or (inherit_from.client_ip if inherit_from else None)
        ua = visitor.user_agent or (inherit_from.user_agent if inherit_from else None)
        origin = visitor.origin or (inherit_from.origin if inherit_from else None)
        lead = CourseAgentLeadRecord(
            agent_id=session.agent_id,
            session_id=session.id,
            consultation_index=index,
            status="open",
            client_ip=ip,
            user_agent=ua,
            origin=origin,
            role=session.role,
            profile_json=build_profile_snapshot(session),
            title=f"客户咨询 #{index}",
            message_count=0,
        )
        self.db.add(lead)
        self.db.flush()
        return lead

    def close_lead(self, lead: CourseAgentLeadRecord, session: CourseAgentSessionRecord) -> None:
        lead.status = "closed"
        lead.ended_at = datetime.now(UTC)
        lead.role = session.role
        lead.profile_json = build_profile_snapshot(session)
        if session.title and session.title not in ("新对话", "对话预览"):
            lead.title = session.title
        lead.updated_at = datetime.now(UTC)

    def ensure_open_lead(
        self,
        session: CourseAgentSessionRecord,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentLeadRecord:
        existing = self.get_open_lead(session.id)
        if existing is not None:
            if visitor:
                if visitor.client_ip and not existing.client_ip:
                    existing.client_ip = visitor.client_ip
                if visitor.user_agent and not existing.user_agent:
                    existing.user_agent = visitor.user_agent
                if visitor.origin and not existing.origin:
                    existing.origin = visitor.origin
            return existing
        return self.open_lead(session, visitor)

    def rotate_on_restart(
        self,
        session: CourseAgentSessionRecord,
        visitor: VisitorContext | None = None,
    ) -> CourseAgentLeadRecord:
        """关闭当前线索并开启新咨询（在状态被清零之前调用以保留画像）。"""
        current = self.get_open_lead(session.id)
        if current is not None:
            self.close_lead(current, session)
        return self.open_lead(session, visitor, inherit_from=current)

    def sync_profile(
        self, lead: CourseAgentLeadRecord, session: CourseAgentSessionRecord
    ) -> None:
        lead.role = session.role
        lead.profile_json = build_profile_snapshot(session)
        if session.title and session.title not in ("新对话", "对话预览"):
            lead.title = session.title
        lead.updated_at = datetime.now(UTC)

    def list_leads(
        self,
        *,
        agent_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CourseAgentLeadSummaryDto]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        stmt = (
            select(CourseAgentLeadRecord, CourseAgentRecord.name)
            .join(
                CourseAgentRecord,
                CourseAgentRecord.agent_id == CourseAgentLeadRecord.agent_id,
            )
            .order_by(CourseAgentLeadRecord.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if agent_id:
            stmt = stmt.where(CourseAgentLeadRecord.agent_id == agent_id)
        rows = self.db.execute(stmt).all()
        return [
            self._to_summary(lead, agent_name=name) for lead, name in rows
        ]

    def get_lead_detail(self, lead_id: uuid.UUID) -> CourseAgentLeadDetailDto:
        lead = self.db.scalar(
            select(CourseAgentLeadRecord)
            .where(CourseAgentLeadRecord.id == lead_id)
            .options(selectinload(CourseAgentLeadRecord.messages))
        )
        if lead is None:
            raise ApiBusinessError("NOT_FOUND", "线索不存在", 404)
        agent = self.db.get(CourseAgentRecord, lead.agent_id)
        agent_name = agent.name if agent else lead.agent_id
        messages = [
            self._to_message_dto(m, agent_id=lead.agent_id) for m in lead.messages
        ]
        summary = self._to_summary(lead, agent_name=agent_name)
        return CourseAgentLeadDetailDto(
            **summary.model_dump(),
            userAgent=lead.user_agent,
            origin=lead.origin,
            messages=messages,
        )

    def delete_lead(self, lead_id: uuid.UUID) -> dict[str, str]:
        lead = self.db.get(CourseAgentLeadRecord, lead_id)
        if lead is None:
            raise ApiBusinessError("NOT_FOUND", "线索不存在", 404)
        # 消息保留在会话中，仅解除与线索的关联（FK ON DELETE SET NULL）
        self.db.delete(lead)
        self.db.commit()
        return {"message": "线索已删除"}

    def _to_summary(
        self, lead: CourseAgentLeadRecord, *, agent_name: str
    ) -> CourseAgentLeadSummaryDto:
        return CourseAgentLeadSummaryDto(
            id=str(lead.id),
            agentId=lead.agent_id,
            agentName=agent_name,
            sessionId=str(lead.session_id),
            consultationIndex=lead.consultation_index,
            status=lead.status,
            clientIp=lead.client_ip,
            role=lead.role,
            profile=dict(lead.profile_json or {}),
            title=lead.title,
            messageCount=lead.message_count or 0,
            startedAt=_iso(lead.started_at),
            endedAt=_iso(lead.ended_at) if lead.ended_at else None,
        )

    def _to_message_dto(
        self, m: CourseAgentMessageRecord, *, agent_id: str
    ) -> CourseAgentMessageDto:
        citations = m.citations_json
        if citations and m.role == "assistant":
            parsed = [
                Citation(
                    c["document"],
                    c["chapter"],
                    attachment_id=c.get("attachmentId"),
                    chunk_id=c.get("chunkId"),
                )
                for c in citations
            ]
            enriched = enrich_citations_with_attachments(self.db, agent_id, parsed)
            if enriched:
                citations = [c.to_dict() for c in enriched]
        return CourseAgentMessageDto(
            id=str(m.id),
            role=m.role,
            content=m.content,
            createdAt=_iso(m.created_at),
            citations=citations,
            quickActions=list(m.quick_actions_json) if m.quick_actions_json else None,
        )
