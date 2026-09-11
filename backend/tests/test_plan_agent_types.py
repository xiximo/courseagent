from types import SimpleNamespace

from app.api.errors import ApiBusinessError
from app.services.billing import (
    apply_tenant_chat_quota,
    require_agent_type_for_plan,
    require_knowledge_base_quota,
    resolve_plan_code,
)


def test_free_org_can_use_basic_agent():
    user = SimpleNamespace(plan_code="free", role_codes=["org_admin"], tenant_id=None)
    require_agent_type_for_plan(user, None, "basic")


def test_free_org_cannot_use_harness_agent():
    user = SimpleNamespace(plan_code="free", role_codes=["org_admin"], tenant_id=None)
    try:
        require_agent_type_for_plan(user, None, "autonomous")
        raise AssertionError("expected PLAN_REQUIRED")
    except ApiBusinessError as exc:
        assert exc.code == "PLAN_REQUIRED"


def test_pro_org_can_use_harness_agent():
    user = SimpleNamespace(plan_code="pro", role_codes=["org_admin"], tenant_id=None)
    require_agent_type_for_plan(user, None, "autonomous")


def test_platform_admin_can_use_harness_on_free_plan():
    user = SimpleNamespace(plan_code="free", role_codes=["sys_admin"], tenant_id=None)
    require_agent_type_for_plan(user, None, "workflow")


def test_free_org_can_create_first_knowledge_base():
    user = SimpleNamespace(plan_code="free", role_codes=["org_admin"], tenant_id=None)
    require_knowledge_base_quota(None, user, used=0)


def test_free_org_cannot_create_second_knowledge_base():
    user = SimpleNamespace(plan_code="free", role_codes=["org_admin"], tenant_id=None)
    try:
        require_knowledge_base_quota(None, user, used=1)
        raise AssertionError("expected PLAN_REQUIRED")
    except ApiBusinessError as exc:
        assert exc.code == "PLAN_REQUIRED"


def test_pro_org_can_create_many_knowledge_bases():
    user = SimpleNamespace(plan_code="pro", role_codes=["org_admin"], tenant_id=None)
    require_knowledge_base_quota(None, user, used=5)


def test_platform_admin_has_unlimited_knowledge_bases():
    user = SimpleNamespace(plan_code="free", role_codes=["sys_admin"], tenant_id=None)
    require_knowledge_base_quota(None, user, used=8)


def test_plan_follows_tenant_not_user():
    user = SimpleNamespace(plan_code="free", role_codes=["org_admin"], tenant_id="tid")
    tenant = SimpleNamespace(plan_code="pro")
    assert resolve_plan_code(user, tenant=tenant) == "pro"


def test_free_tenant_monthly_quota_resets_on_new_month():
    tenant = SimpleNamespace(plan_code="free", chat_count=50, usage_year_month="2026-08")
    apply_tenant_chat_quota(tenant, year_month="2026-09")
    assert tenant.chat_count == 1
    assert tenant.usage_year_month == "2026-09"


def test_free_tenant_monthly_quota_blocks_at_50():
    tenant = SimpleNamespace(plan_code="free", chat_count=50, usage_year_month="2026-09")
    try:
        apply_tenant_chat_quota(tenant, year_month="2026-09")
        raise AssertionError("expected QUOTA_EXCEEDED")
    except ApiBusinessError as exc:
        assert exc.code == "QUOTA_EXCEEDED"


def test_pro_tenant_has_unlimited_monthly_chats():
    tenant = SimpleNamespace(plan_code="pro", chat_count=80, usage_year_month="2026-09")
    apply_tenant_chat_quota(tenant, year_month="2026-09")
    assert tenant.chat_count == 81
