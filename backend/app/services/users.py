from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.db.models.user import AccountStatus, User
from app.schemas.auth import AuthUserProfile
from app.schemas.users import UserAccountDto, UserPersonaProfileDto
from app.services.password import hash_password
from app.services.persona_users import PERSONA_USERS, TEST_USER_PASSWORD

SEED_USERNAMES = {item["username"] for item in PERSONA_USERS}


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


def _profile_dict(user: User) -> dict:
    raw = user.profile_json if isinstance(user.profile_json, dict) else {}
    return raw or {}


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


def to_user_account_dto(user: User) -> UserAccountDto:
    profile = UserPersonaProfileDto.model_validate(_profile_dict(user))
    return UserAccountDto(
        id=str(user.id),
        username=user.username,
        fullName=user.full_name,
        status=user.status.value,
        roleCodes=list(user.role_codes or []),
        profile=profile,
        lastLoginAt=user.last_login_at.isoformat() if user.last_login_at else None,
        createdAt=user.created_at.isoformat() if user.created_at else None,
        isSeed=user.username in SEED_USERNAMES,
    )


def list_users(db: Session) -> list[UserAccountDto]:
    rows = db.scalars(select(User).order_by(User.created_at.asc())).all()
    return [to_user_account_dto(row) for row in rows]


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    full_name: str,
    status: AccountStatus,
    role_codes: list[str],
    profile: dict,
) -> User:
    name = username.strip()
    if get_user_by_username(db, name):
        raise ApiBusinessError("USERNAME_TAKEN", "用户名已存在", 409)
    user = User(
        username=name,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        status=status,
        role_codes=role_codes or ["end_user"],
        profile_json=profile or {},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user: User,
    *,
    full_name: str | None = None,
    status: AccountStatus | None = None,
    role_codes: list[str] | None = None,
    profile: dict | None = None,
    password: str | None = None,
) -> User:
    if full_name is not None:
        user.full_name = full_name.strip()
    if status is not None:
        if _is_admin(user) and status != AccountStatus.enabled:
            remaining = _enabled_admin_count(db, exclude_id=user.id)
            if remaining <= 0:
                raise ApiBusinessError("LAST_ADMIN", "不能禁用最后一个管理员", 400)
        user.status = status
    if role_codes is not None:
        user.role_codes = role_codes
    if profile is not None:
        user.profile_json = profile
    if password:
        user.password_hash = hash_password(password)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    if _is_admin(user):
        remaining = _enabled_admin_count(db, exclude_id=user.id)
        if remaining <= 0:
            raise ApiBusinessError("LAST_ADMIN", "不能删除最后一个管理员", 400)
    db.delete(user)
    db.commit()


def reset_user_password(db: Session, user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    db.commit()


def _is_admin(user: User) -> bool:
    codes = {str(code).lower() for code in (user.role_codes or [])}
    return bool(codes & {"sys_admin", "system_admin", "admin"})


def _enabled_admin_count(db: Session, *, exclude_id: UUID) -> int:
    rows = db.scalars(
        select(User).where(
            User.id != exclude_id,
            User.status == AccountStatus.enabled,
        )
    ).all()
    return sum(1 for row in rows if _is_admin(row))


def ensure_persona_test_users(db: Session) -> None:
    for item in PERSONA_USERS:
        username = item["username"]
        existing = get_user_by_username(db, username)
        if existing:
            existing.full_name = item["fullName"]
            existing.role_codes = list(item["roleCodes"])
            current = existing.profile_json if isinstance(existing.profile_json, dict) else {}
            if not current:
                existing.profile_json = dict(item["profile"])
            continue
        db.add(
            User(
                username=username,
                password_hash=hash_password(TEST_USER_PASSWORD),
                full_name=item["fullName"],
                status=AccountStatus.enabled,
                role_codes=list(item["roleCodes"]),
                profile_json=dict(item["profile"]),
            )
        )
    db.commit()


def touch_last_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)


def ensure_login_allowed(user: User) -> None:
    if user.status != AccountStatus.enabled:
        raise ValueError("账号已禁用或不可用")
