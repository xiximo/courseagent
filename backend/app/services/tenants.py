from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.config import get_settings
from app.course_agent.material_service import MaterialService, _owner_key
from app.db.models.course_agent import CourseAgentRecord
from app.db.models.course_agent_resources import CourseAgentKnowledgeBaseRecord
from app.db.models.tenant import TenantRecord
from app.db.models.user import AccountStatus, User
from app.schemas.auth import AuthUserProfile, LoginResponse
from app.schemas.tenants import (
    CreateOrgMemberBody,
    OrgMemberDto,
    OrgWorkspaceDto,
    PublicTenantDto,
    RegisterMemberBody,
    RegisterOrgBody,
    TenantSummaryDto,
)
from app.services.billing import PLAN_FREE, PLAN_PRO, normalize_plan
from app.services.password import hash_password
from app.services.tenant_scope import ORG_ADMIN_ROLE, TenantScope, resolve_tenant_scope
from app.services.tenant_workspace import ensure_first_user_is_tenant_admin
from app.services.users import create_user, get_user_by_username, to_auth_profile
from app.api.deps import create_access_token


def to_auth_profile_with_tenant(db: Session, user: User) -> AuthUserProfile:
    profile = to_auth_profile(user)
    tenant = db.get(TenantRecord, user.tenant_id) if user.tenant_id else None
    profile.tenantId = str(tenant.id) if tenant else None
    profile.tenantName = tenant.name if tenant else None
    profile.tenantSlug = tenant.slug if tenant else None
    if tenant is not None:
        profile.planCode = tenant.plan_code or "free"
    return profile


def _unique_slug(db: Session, org_name: str) -> str:
    token = uuid.uuid4().hex[:8]
    compact = re.sub(r"[^a-zA-Z0-9]+", "-", org_name.strip().lower()).strip("-")
    prefix = compact[:24] if re.search(r"[a-z0-9]", compact) else "org"
    slug = f"{prefix}-{token}"
    while db.scalar(select(TenantRecord.id).where(TenantRecord.slug == slug)):
        slug = f"{prefix}-{uuid.uuid4().hex[:8]}"
    return slug


def register_organization(db: Session, body: RegisterOrgBody) -> LoginResponse:
    org_name = body.orgName.strip()
    contact = body.contactName.strip()
    username = body.username.strip()
    password = body.password.strip()
    if len(org_name) < 2:
        raise ApiBusinessError("INVALID_ORG", "请填写机构名称", 400)
    if len(contact) < 2:
        raise ApiBusinessError("INVALID_CONTACT", "请填写联系人姓名", 400)
    if len(username) < 2:
        raise ApiBusinessError("INVALID_USERNAME", "用户名至少 2 位", 400)
    if len(password) < 6:
        raise ApiBusinessError("WEAK_PASSWORD", "密码至少 6 位", 400)
    if get_user_by_username(db, username):
        raise ApiBusinessError("USERNAME_TAKEN", "用户名已存在，请换一个", 409)

    tenant = TenantRecord(name=org_name, slug=_unique_slug(db, org_name))
    db.add(tenant)
    db.flush()
    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=contact,
        status=AccountStatus.enabled,
        role_codes=[ORG_ADMIN_ROLE],
        tenant_id=tenant.id,
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    ensure_first_user_is_tenant_admin(db, tenant.id)
    db.commit()
    db.refresh(user)

    settings = get_settings()
    return LoginResponse(
        accessToken=create_access_token(user.username, settings),
        tokenType="Bearer",
        expiresInSeconds=settings.jwt_expire_seconds,
        user=to_auth_profile_with_tenant(db, user),
    )


def list_tenants(db: Session) -> list[TenantSummaryDto]:
    user_count = (
        select(func.count(User.id))
        .where(User.tenant_id == TenantRecord.id)
        .correlate(TenantRecord)
        .scalar_subquery()
    )
    owner_name = (
        select(User.username)
        .where(User.tenant_id == TenantRecord.id)
        .order_by(User.created_at.asc())
        .limit(1)
        .correlate(TenantRecord)
        .scalar_subquery()
    )
    rows = db.execute(
        select(
            TenantRecord,
            user_count.label("user_count"),
            owner_name.label("owner_username"),
        ).order_by(TenantRecord.created_at.desc())
    ).all()
    result: list[TenantSummaryDto] = []
    for tenant, count, owner in rows:
        result.append(
            TenantSummaryDto(
                id=str(tenant.id),
                name=tenant.name,
                slug=tenant.slug,
                ownerUsername=str(owner or ""),
                planCode=str(tenant.plan_code or "free"),
                userCount=int(count or 0),
                createdAt=tenant.created_at.isoformat() if tenant.created_at else "",
            )
        )
    return result


def _get_tenant(db: Session, tenant_id: uuid.UUID) -> TenantRecord:
    tenant = db.get(TenantRecord, tenant_id)
    if tenant is None:
        raise ApiBusinessError("NOT_FOUND", "机构不存在", 404)
    return tenant


def _to_tenant_summary(db: Session, tenant: TenantRecord) -> TenantSummaryDto:
    count = db.scalar(
        select(func.count(User.id)).where(User.tenant_id == tenant.id)
    )
    owner = db.scalar(
        select(User.username)
        .where(User.tenant_id == tenant.id)
        .order_by(User.created_at.asc())
        .limit(1)
    )
    return TenantSummaryDto(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        ownerUsername=str(owner or ""),
        planCode=str(tenant.plan_code or PLAN_FREE),
        userCount=int(count or 0),
        createdAt=tenant.created_at.isoformat() if tenant.created_at else "",
    )


def set_tenant_plan(db: Session, tenant_id: uuid.UUID, plan_code: str) -> TenantSummaryDto:
    tenant = _get_tenant(db, tenant_id)
    code = normalize_plan(plan_code)
    tenant.plan_code = code
    tenant.plan_upgraded_at = datetime.now(UTC) if code == PLAN_PRO else None
    db.commit()
    db.refresh(tenant)
    return _to_tenant_summary(db, tenant)


def delete_tenant(db: Session, tenant_id: uuid.UUID) -> None:
    tenant = _get_tenant(db, tenant_id)
    agents = list(
        db.scalars(
            select(CourseAgentRecord).where(CourseAgentRecord.tenant_id == tenant_id)
        )
    )
    for agent in agents:
        db.delete(agent)
    db.flush()

    material = MaterialService(
        db, scope=TenantScope(tenant_id=tenant_id, is_platform=False)
    )
    kbs = list(
        db.scalars(
            select(CourseAgentKnowledgeBaseRecord).where(
                CourseAgentKnowledgeBaseRecord.tenant_id == tenant_id
            )
        )
    )
    for kb in kbs:
        material_label = kb.material_label
        standard_id = kb.standard_id
        owner = _owner_key(kb.agent_id)
        db.delete(kb)
        db.flush()
        material._purge_standard_material(owner, material_label, standard_id)

    users = list(db.scalars(select(User).where(User.tenant_id == tenant_id)))
    for user in users:
        db.delete(user)
    db.delete(tenant)
    db.commit()


def get_tenant_by_slug(db: Session, slug: str) -> TenantRecord:
    token = slug.strip()
    if not token:
        raise ApiBusinessError("INVALID_SLUG", "邀请链接无效", 400)
    tenant = db.scalar(select(TenantRecord).where(TenantRecord.slug == token))
    if tenant is None:
        raise ApiBusinessError("NOT_FOUND", "机构不存在或邀请链接已失效", 404)
    return tenant


def get_public_tenant(db: Session, slug: str) -> PublicTenantDto:
    tenant = get_tenant_by_slug(db, slug)
    return PublicTenantDto(name=tenant.name, slug=tenant.slug)


def require_org_admin_scope(profile: AuthUserProfile) -> TenantScope:
    scope = resolve_tenant_scope(profile)
    codes = {str(code).lower() for code in (profile.roleCodes or [])}
    if scope.is_platform or scope.tenant_id is None or ORG_ADMIN_ROLE not in codes:
        raise ApiBusinessError("FORBIDDEN", "仅机构管理员可管理本机构成员", 403)
    return scope


def _to_org_member(user: User) -> OrgMemberDto:
    return OrgMemberDto(
        id=str(user.id),
        username=user.username,
        fullName=user.full_name,
        status=user.status.value,
        roleCodes=list(user.role_codes or []),
        lastLoginAt=user.last_login_at.isoformat() if user.last_login_at else None,
        createdAt=user.created_at.isoformat() if user.created_at else None,
    )


def get_org_workspace(db: Session, profile: AuthUserProfile) -> OrgWorkspaceDto:
    scope = resolve_tenant_scope(profile)
    if scope.tenant_id is None:
        raise ApiBusinessError("NO_TENANT", "当前账号不属于任何机构", 400)
    tenant = _get_tenant(db, scope.tenant_id)
    count = db.scalar(select(func.count(User.id)).where(User.tenant_id == tenant.id))
    return OrgWorkspaceDto(
        tenantId=str(tenant.id),
        tenantName=tenant.name,
        slug=tenant.slug,
        planCode=str(tenant.plan_code or PLAN_FREE),
        userCount=int(count or 0),
        joinPath=f"/join/{tenant.slug}",
    )


def list_org_members(db: Session, profile: AuthUserProfile) -> list[OrgMemberDto]:
    scope = require_org_admin_scope(profile)
    rows = db.scalars(
        select(User)
        .where(User.tenant_id == scope.tenant_id)
        .order_by(User.created_at.asc())
    ).all()
    return [_to_org_member(row) for row in rows]


def create_org_member(
    db: Session, profile: AuthUserProfile, body: CreateOrgMemberBody
) -> OrgMemberDto:
    scope = require_org_admin_scope(profile)
    user = create_user(
        db,
        username=body.username,
        password=body.password,
        full_name=body.fullName,
        status=AccountStatus.enabled,
        role_codes=["end_user"],
        profile={},
        tenant_id=scope.tenant_id,
    )
    return _to_org_member(user)


def register_member(db: Session, body: RegisterMemberBody) -> LoginResponse:
    tenant = get_tenant_by_slug(db, body.slug)
    username = body.username.strip()
    password = body.password.strip()
    full_name = body.fullName.strip()
    if len(full_name) < 1:
        raise ApiBusinessError("INVALID_CONTACT", "请填写姓名", 400)
    if len(username) < 2:
        raise ApiBusinessError("INVALID_USERNAME", "用户名至少 2 位", 400)
    if len(password) < 6:
        raise ApiBusinessError("WEAK_PASSWORD", "密码至少 6 位", 400)
    user = create_user(
        db,
        username=username,
        password=password,
        full_name=full_name,
        status=AccountStatus.enabled,
        role_codes=["end_user"],
        profile={},
        tenant_id=tenant.id,
    )
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    settings = get_settings()
    return LoginResponse(
        accessToken=create_access_token(user.username, settings),
        tokenType="Bearer",
        expiresInSeconds=settings.jwt_expire_seconds,
        user=to_auth_profile_with_tenant(db, user),
    )
