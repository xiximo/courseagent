from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.tenants import (
    DeleteTenantResultDto,
    TenantSummaryDto,
    UpdateTenantPlanBody,
)
from app.services.tenants import delete_tenant, list_tenants, set_tenant_plan

router = APIRouter(tags=["tenants"])

_PLATFORM_ROLES = {"sys_admin", "system_admin", "admin"}


def _require_platform(
    user: Annotated[AuthUserProfile, Depends(get_current_user)],
) -> AuthUserProfile:
    codes = {code.lower() for code in user.roleCodes}
    if not (codes & _PLATFORM_ROLES):
        raise ApiBusinessError("FORBIDDEN", "仅平台管理员可管理租户", 403)
    return user


def _parse_tenant_id(tenant_id: str) -> UUID:
    try:
        return UUID(tenant_id)
    except ValueError as exc:
        raise ApiBusinessError("INVALID_ID", "机构 ID 无效", 400) from exc


@router.get("/api/v1/platform/tenants", response_model=ApiResponse[list[TenantSummaryDto]])
def get_platform_tenants(
    _: Annotated[AuthUserProfile, Depends(_require_platform)],
    db: Session = Depends(get_db),
):
    return success(list_tenants(db))


@router.patch(
    "/api/v1/platform/tenants/{tenant_id}/plan",
    response_model=ApiResponse[TenantSummaryDto],
)
def patch_platform_tenant_plan(
    tenant_id: str,
    body: UpdateTenantPlanBody,
    _: Annotated[AuthUserProfile, Depends(_require_platform)],
    db: Session = Depends(get_db),
):
    return success(
        set_tenant_plan(db, _parse_tenant_id(tenant_id), body.planCode),
        message="套餐已更新",
    )


@router.delete(
    "/api/v1/platform/tenants/{tenant_id}",
    response_model=ApiResponse[DeleteTenantResultDto],
)
def delete_platform_tenant(
    tenant_id: str,
    _: Annotated[AuthUserProfile, Depends(_require_platform)],
    db: Session = Depends(get_db),
):
    delete_tenant(db, _parse_tenant_id(tenant_id))
    return success(DeleteTenantResultDto())
