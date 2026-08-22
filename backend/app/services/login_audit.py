from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.login_audit import LoginAuditLog
from app.db.models.user import User
from app.schemas.audit import LoginAuditDto


def resolve_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        stripped = real_ip.strip()
        if stripped:
            return stripped[:64]
    if request.client and request.client.host:
        return str(request.client.host)[:64]
    return ""


def record_login(
    db: Session,
    user: User,
    ip_address: str,
    *,
    logged_in_at: datetime | None = None,
) -> LoginAuditLog:
    row = LoginAuditLog(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name or "",
        ip_address=(ip_address or "")[:64],
        logged_in_at=logged_in_at or datetime.now(UTC),
    )
    db.add(row)
    return row


def to_login_audit_dto(row: LoginAuditLog) -> LoginAuditDto:
    logged_in_at = row.logged_in_at
    if logged_in_at is not None and logged_in_at.tzinfo is None:
        logged_in_at = logged_in_at.replace(tzinfo=UTC)
    return LoginAuditDto(
        id=str(row.id),
        username=row.username,
        fullName=row.full_name or "",
        ipAddress=row.ip_address or "",
        loggedInAt=logged_in_at.isoformat() if logged_in_at else "",
    )


def list_login_audits(db: Session, *, limit: int = 200) -> list[LoginAuditDto]:
    size = max(1, min(limit, 500))
    rows = db.scalars(
        select(LoginAuditLog)
        .order_by(LoginAuditLog.logged_in_at.desc())
        .limit(size)
    ).all()
    return [to_login_audit_dto(row) for row in rows]
