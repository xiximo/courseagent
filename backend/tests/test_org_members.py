from uuid import uuid4

import pytest

from app.api.errors import ApiBusinessError
from app.schemas.auth import AuthUserProfile
from app.services.tenants import require_org_admin_scope


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


def test_org_admin_can_manage_members():
    tenant = uuid4()
    scope = require_org_admin_scope(
        _profile(roleCodes=["org_admin"], tenantId=str(tenant))
    )
    assert scope.tenant_id == tenant
    assert not scope.is_platform


def test_member_cannot_manage_members():
    with pytest.raises(ApiBusinessError) as exc:
        require_org_admin_scope(
            _profile(roleCodes=["end_user"], tenantId=str(uuid4()))
        )
    assert exc.value.code == "FORBIDDEN"


def test_platform_admin_cannot_use_org_member_api():
    with pytest.raises(ApiBusinessError) as exc:
        require_org_admin_scope(_profile(roleCodes=["sys_admin"]))
    assert exc.value.code == "FORBIDDEN"
