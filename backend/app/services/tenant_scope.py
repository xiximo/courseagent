from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.db.models.course_agent import CourseAgentRecord
from app.db.models.course_agent_resources import CourseAgentKnowledgeBaseRecord
from app.schemas.auth import AuthUserProfile

PLATFORM_ROLES = {"sys_admin", "system_admin", "admin"}
ORG_ADMIN_ROLE = "org_admin"


@dataclass(frozen=True)
class TenantScope:
    tenant_id: UUID | None
    is_platform: bool

    @staticmethod
    def unrestricted() -> TenantScope:
        return TenantScope(tenant_id=None, is_platform=True)

    def allows_resource(self, resource_tenant_id: UUID | None) -> bool:
        if self.is_platform:
            return True
        if self.tenant_id is None:
            return resource_tenant_id is None
        return resource_tenant_id == self.tenant_id


def is_platform_user(role_codes: list[str] | None) -> bool:
    codes = {str(code).lower() for code in (role_codes or [])}
    return bool(codes & PLATFORM_ROLES)


def parse_tenant_id(profile: AuthUserProfile | None) -> UUID | None:
    if profile is None or not profile.tenantId:
        return None
    try:
        return UUID(str(profile.tenantId))
    except ValueError:
        return None


def resolve_tenant_scope(profile: AuthUserProfile) -> TenantScope:
    return TenantScope(
        tenant_id=parse_tenant_id(profile),
        is_platform=is_platform_user(profile.roleCodes),
    )


def first_user_role_codes(existing_count: int, role_codes: list[str] | None) -> list[str]:
    roles = list(role_codes or ["end_user"])
    lowered = {str(code).lower() for code in roles}
    if existing_count == 0 and ORG_ADMIN_ROLE not in lowered and not is_platform_user(roles):
        return [ORG_ADMIN_ROLE, *roles]
    return roles


def apply_agent_tenant_filter(stmt, scope: TenantScope):
    if scope.is_platform or scope.tenant_id is None:
        return stmt.where(CourseAgentRecord.tenant_id.is_(None))
    return stmt.where(CourseAgentRecord.tenant_id == scope.tenant_id)


def apply_kb_tenant_filter(stmt, scope: TenantScope):
    if scope.is_platform:
        return stmt
    if scope.tenant_id is not None:
        return stmt.where(CourseAgentKnowledgeBaseRecord.tenant_id == scope.tenant_id)
    return stmt.where(CourseAgentKnowledgeBaseRecord.tenant_id.is_(None))
