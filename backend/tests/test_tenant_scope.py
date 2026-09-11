from uuid import uuid4

from sqlalchemy import select

from app.db.models.course_agent import CourseAgentRecord
from app.schemas.auth import AuthUserProfile
from app.services.tenant_scope import (
    TenantScope,
    apply_agent_tenant_filter,
    first_user_role_codes,
    resolve_tenant_scope,
)
from app.services.tenant_workspace import _detach_shared_knowledge


def _profile(**kwargs) -> AuthUserProfile:
    payload = {
        "id": str(uuid4()),
        "username": "demo",
        "fullName": "演示",
        "roleCodes": ["org_admin"],
        "planCode": "free",
    }
    payload.update(kwargs)
    return AuthUserProfile.model_validate(payload)


def test_first_user_becomes_org_admin():
    assert first_user_role_codes(0, ["end_user"]) == ["org_admin", "end_user"]
    assert first_user_role_codes(1, ["end_user"]) == ["end_user"]
    assert first_user_role_codes(0, ["org_admin"]) == ["org_admin"]
    assert first_user_role_codes(0, ["sys_admin"]) == ["sys_admin"]


def test_org_scope_only_allows_same_tenant():
    tenant = uuid4()
    other = uuid4()
    scope = resolve_tenant_scope(
        _profile(roleCodes=["org_admin"], tenantId=str(tenant))
    )
    assert scope.tenant_id == tenant
    assert not scope.is_platform
    assert scope.allows_resource(tenant)
    assert not scope.allows_resource(other)
    assert not scope.allows_resource(None)


def test_platform_scope_allows_all_resources():
    scope = resolve_tenant_scope(_profile(roleCodes=["sys_admin"]))
    assert scope.is_platform
    assert scope.allows_resource(None)
    assert scope.allows_resource(uuid4())


def test_unscoped_user_only_sees_platform_templates():
    scope = resolve_tenant_scope(_profile(roleCodes=["end_user"]))
    assert not scope.is_platform
    assert scope.tenant_id is None
    assert scope.allows_resource(None)
    assert not scope.allows_resource(uuid4())


def test_clone_strips_shared_knowledge_ids():
    cfg = _detach_shared_knowledge(
        {
            "boundKnowledgeBaseIds": ["kb_shared"],
            "reactConfig": {"tools": [{"knowledgeBaseIds": ["kb_shared"]}]},
            "workflowGraph": {"nodes": [{"data": {"knowledgeBaseId": "kb_shared"}}]},
        }
    )
    assert cfg["boundKnowledgeBaseIds"] == []
    assert cfg["reactConfig"]["tools"][0]["knowledgeBaseIds"] == []
    assert cfg["workflowGraph"]["nodes"][0]["data"]["knowledgeBaseId"] is None


def test_unrestricted_scope_is_platform():
    scope = TenantScope.unrestricted()
    assert scope.is_platform
    assert scope.allows_resource(uuid4())


def test_agent_list_filter_is_tenant_scoped():
    org = uuid4()
    org_sql = str(
        apply_agent_tenant_filter(
            select(CourseAgentRecord.agent_id),
            TenantScope(tenant_id=org, is_platform=False),
        ).compile(compile_kwargs={"literal_binds": True})
    )
    platform_sql = str(
        apply_agent_tenant_filter(
            select(CourseAgentRecord.agent_id),
            TenantScope(tenant_id=None, is_platform=True),
        ).compile(compile_kwargs={"literal_binds": True})
    )
    assert "tenant_id" in org_sql
    assert org.hex in org_sql.replace("-", "")
    assert "IS NULL" in platform_sql.upper()
