from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.schemas.tenants import (
    CreateOrgMemberBody,
    OrgMemberDto,
    OrgWorkspaceDto,
    PublicTenantDto,
)
from app.services.tenants import (
    create_org_member,
    get_org_workspace,
    get_public_tenant,
    list_org_members,
)

router = APIRouter(tags=["org"])


@router.get("/api/v1/org/public/{slug}", response_model=ApiResponse[PublicTenantDto])
def get_public_org(slug: str, db: Session = Depends(get_db)):
    return success(get_public_tenant(db, slug))


@router.get("/api/v1/org/me", response_model=ApiResponse[OrgWorkspaceDto])
def get_my_org(
    current_user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(get_org_workspace(db, current_user))


@router.get("/api/v1/org/members", response_model=ApiResponse[list[OrgMemberDto]])
def get_org_members(
    current_user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(list_org_members(db, current_user))


@router.post("/api/v1/org/members", response_model=ApiResponse[OrgMemberDto])
def post_org_member(
    body: CreateOrgMemberBody,
    current_user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(create_org_member(db, current_user, body), message="成员已创建")
