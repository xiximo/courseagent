from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.db.session import get_db
from app.schemas.audit import LoginAuditDto
from app.schemas.auth import AuthUserProfile
from app.schemas.common import ApiResponse, success
from app.services.login_audit import list_login_audits

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

_ADMIN_ROLES = {"sys_admin", "system_admin", "admin"}


def require_admin(
    current_user: Annotated[AuthUserProfile, Depends(get_current_user)],
) -> AuthUserProfile:
    codes = {code.lower() for code in current_user.roleCodes}
    if not (codes & _ADMIN_ROLES):
        raise ApiBusinessError("FORBIDDEN", "仅管理员可查看审计日志", 403)
    return current_user


@router.get("/login-logs", response_model=ApiResponse[list[LoginAuditDto]])
def get_login_logs(
    _: Annotated[AuthUserProfile, Depends(require_admin)],
    db: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=500),
):
    return success(list_login_audits(db, limit=limit))
