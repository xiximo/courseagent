from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.models.user import AccountStatus
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.users import (
    CreateUserBody,
    DeleteUserResultDto,
    ResetUserPasswordResultDto,
    UpdateUserBody,
    UserAccountDto,
)
from app.services.persona_users import TEST_USER_PASSWORD
from app.services.users import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    reset_user_password,
    to_user_account_dto_with_tenant,
    update_user,
)

router = APIRouter(prefix="/api/v1/users", tags=["users"])

_ADMIN_ROLES = {"sys_admin", "system_admin", "admin"}


def require_admin(
    current_user: Annotated[AuthUserProfile, Depends(get_current_user)],
) -> AuthUserProfile:
    codes = {code.lower() for code in current_user.roleCodes}
    if not (codes & _ADMIN_ROLES):
        raise ApiBusinessError("FORBIDDEN", "仅管理员可管理用户", 403)
    return current_user


def _parse_status(value: str) -> AccountStatus:
    try:
        return AccountStatus(value)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_STATUS", "无效的账号状态", 400) from exc


@router.get("", response_model=ApiResponse[list[UserAccountDto]])
def get_users(
    _: Annotated[AuthUserProfile, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    return success(list_users(db))


@router.post("", response_model=ApiResponse[UserAccountDto])
def post_user(
    body: CreateUserBody,
    _: Annotated[AuthUserProfile, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    user = create_user(
        db,
        username=body.username,
        password=body.password,
        full_name=body.fullName,
        status=_parse_status(body.status),
        role_codes=body.roleCodes,
        profile=body.profile.model_dump(),
    )
    return success(to_user_account_dto_with_tenant(db, user), message="用户已创建")


@router.patch("/{user_id}", response_model=ApiResponse[UserAccountDto])
def patch_user(
    user_id: UUID,
    body: UpdateUserBody,
    _: Annotated[AuthUserProfile, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ApiBusinessError("NOT_FOUND", "用户不存在", 404)
    updated = update_user(
        db,
        user,
        full_name=body.fullName,
        status=_parse_status(body.status) if body.status else None,
        role_codes=body.roleCodes,
        profile=body.profile.model_dump() if body.profile else None,
        password=body.password,
    )
    return success(to_user_account_dto_with_tenant(db, updated), message="用户已更新")


@router.delete("/{user_id}", response_model=ApiResponse[DeleteUserResultDto])
def remove_user(
    user_id: UUID,
    _: Annotated[AuthUserProfile, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ApiBusinessError("NOT_FOUND", "用户不存在", 404)
    delete_user(db, user)
    return success(DeleteUserResultDto())


@router.post(
    "/{user_id}/reset-password",
    response_model=ApiResponse[ResetUserPasswordResultDto],
)
def post_reset_password(
    user_id: UUID,
    _: Annotated[AuthUserProfile, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ApiBusinessError("NOT_FOUND", "用户不存在", 404)
    reset_user_password(db, user, TEST_USER_PASSWORD)
    return success(
        ResetUserPasswordResultDto(
            message="密码已重置为测试口令",
            password=TEST_USER_PASSWORD,
        )
    )
