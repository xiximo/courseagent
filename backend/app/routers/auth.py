from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import create_access_token, get_current_user
from app.api.errors import ApiBusinessError
from app.config import Settings, get_settings
from app.db.models.user import AccountStatus
from app.db.session import get_db
from app.schemas.auth import (
    AuthUserProfile,
    ChangePasswordBody,
    ChangePasswordResultDto,
    LoginBody,
    LoginResponse,
)
from app.schemas.common import ApiResponse, success
from app.services.password import hash_password, verify_password
from app.services.users import get_user_by_username, to_auth_profile

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[LoginResponse])
def login(
    body: LoginBody,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Session = Depends(get_db),
):
    username = body.username.strip()
    user = get_user_by_username(db, username)

    if not user or not verify_password(body.password, user.password_hash):
        raise ApiBusinessError("INVALID_CREDENTIALS", "用户名或密码错误", 401)

    if user.status != AccountStatus.enabled:
        raise ApiBusinessError("ACCOUNT_DISABLED", "账号已禁用或不可用", 403)

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)

    profile = to_auth_profile(user)
    token = create_access_token(user.username, settings)

    return success(
        LoginResponse(
            accessToken=token,
            tokenType="Bearer",
            expiresInSeconds=settings.jwt_expire_seconds,
            user=profile,
        )
    )


@router.get("/me", response_model=ApiResponse[AuthUserProfile])
def me(current_user: Annotated[AuthUserProfile, Depends(get_current_user)]):
    return success(current_user)


@router.post(
    "/change-password",
    response_model=ApiResponse[ChangePasswordResultDto],
)
def change_password(
    body: ChangePasswordBody,
    current_user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    user = get_user_by_username(db, current_user.username)
    if user is None or user.status != AccountStatus.enabled:
        raise ApiBusinessError("UNAUTHORIZED", "用户不存在或已失效", 401)

    current = (body.currentPassword or "").strip()
    new_password = (body.newPassword or "").strip()
    if not current:
        raise ApiBusinessError("INVALID_PASSWORD", "请输入当前密码", 400)
    if len(new_password) < 6:
        raise ApiBusinessError("WEAK_PASSWORD", "新密码至少 6 位", 400)
    if not verify_password(current, user.password_hash):
        raise ApiBusinessError("INVALID_PASSWORD", "当前密码不正确", 400)
    if verify_password(new_password, user.password_hash):
        raise ApiBusinessError("SAME_PASSWORD", "新密码不能与当前密码相同", 400)

    user.password_hash = hash_password(new_password)
    db.commit()
    return success(ChangePasswordResultDto(changed=True), message="密码已更新")
