from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.config import Settings, get_settings
from app.db.models.user import AccountStatus
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.services.users import get_user_by_username, to_auth_profile

ALGORITHM = "HS256"


def create_access_token(
    subject: str,
    settings: Settings,
    extra: dict | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(seconds=settings.jwt_expire_seconds)
    payload = {"sub": subject, "exp": expire, **(extra or {})}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ApiBusinessError("UNAUTHORIZED", "登录已失效，请重新登录", 401) from exc


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[Settings, Depends(get_settings)] = ...,
    db: Session = Depends(get_db),
) -> AuthUserProfile:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiBusinessError("UNAUTHORIZED", "未登录或令牌无效", 401)

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token, settings)
    username = payload.get("sub")
    if not username:
        raise ApiBusinessError("UNAUTHORIZED", "用户不存在或已失效", 401)

    user = get_user_by_username(db, str(username))
    if not user or user.status != AccountStatus.enabled:
        raise ApiBusinessError("UNAUTHORIZED", "用户不存在或已失效", 401)

    return to_auth_profile(user)
