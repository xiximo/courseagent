from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import AccountStatus, User
from app.schemas.auth import AuthUserProfile


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def to_auth_profile(user: User) -> AuthUserProfile:
    return AuthUserProfile(
        id=str(user.id),
        username=user.username,
        fullName=user.full_name,
        employeeNo=user.employee_no,
        deptId=user.dept_id,
        status=user.status.value,
        roleCodes=list(user.role_codes or []),
        lastLoginAt=user.last_login_at.isoformat() if user.last_login_at else None,
    )


def touch_last_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)


def ensure_login_allowed(user: User) -> None:
    if user.status != AccountStatus.enabled:
        raise ValueError("账号已禁用或不可用")
