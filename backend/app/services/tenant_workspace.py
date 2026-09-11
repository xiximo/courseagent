from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.course_agent import CourseAgentRecord
from app.db.models.user import User
from app.services.tenant_scope import ORG_ADMIN_ROLE, is_platform_user


def ensure_first_user_is_tenant_admin(db: Session, tenant_id: UUID) -> None:
    users = list(
        db.scalars(
            select(User)
            .where(User.tenant_id == tenant_id)
            .order_by(User.created_at.asc())
        )
    )
    if not users:
        return
    if any(ORG_ADMIN_ROLE in (user.role_codes or []) for user in users):
        return
    first = users[0]
    if is_platform_user(first.role_codes):
        return
    codes = [str(code) for code in (first.role_codes or []) if str(code) != ORG_ADMIN_ROLE]
    first.role_codes = [ORG_ADMIN_ROLE, *codes]


def backfill_tenant_admins(db: Session) -> None:
    from app.db.models.tenant import TenantRecord

    tenant_ids = list(db.scalars(select(TenantRecord.id)))
    for tenant_id in tenant_ids:
        ensure_first_user_is_tenant_admin(db, tenant_id)
    db.commit()


def ensure_tenant_workspace(
    db: Session, tenant_id: UUID, *, commit: bool = False
) -> CourseAgentRecord | None:
    del commit
    return db.scalar(
        select(CourseAgentRecord).where(CourseAgentRecord.tenant_id == tenant_id)
    )


def _detach_shared_knowledge(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict = {}
        for key, item in value.items():
            lowered = str(key)
            if lowered in {
                "boundKnowledgeBaseIds",
                "knowledgeBaseIds",
            }:
                cleaned[key] = []
            elif lowered in {
                "knowledgeBaseId",
                "activeKnowledgeBaseId",
                "kbId",
                "kb_id",
            }:
                cleaned[key] = None
            else:
                cleaned[key] = _detach_shared_knowledge(item)
        return cleaned
    if isinstance(value, list):
        return [_detach_shared_knowledge(item) for item in value]
    return value
