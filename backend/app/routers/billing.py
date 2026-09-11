from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.errors import ApiBusinessError
from app.config import get_settings
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import AuthUserProfile
from app.schemas.billing import (
    AdminUsageStatsDto,
    AlipayPagePayDto,
    BillingMeDto,
    BillingOrderDto,
    BillingPayOptionsDto,
    BillingPlanDto,
    CreateBillingOrderBody,
    StripeCheckoutDto,
)
from app.schemas.common import ApiResponse, success
from app.services.billing import (
    create_order,
    get_admin_usage_stats,
    get_billing_me,
    get_pay_options,
    handle_alipay_notify,
    handle_alipay_return,
    handle_stripe_return,
    list_plans,
    mock_pay_order,
    start_alipay_page_pay,
    start_stripe_checkout,
)
from app.services.tenant_scope import resolve_tenant_scope
from app.services.users import get_user_by_id

router = APIRouter(tags=["billing"])

_ADMIN_ROLES = {"sys_admin", "system_admin", "admin", "org_admin"}


def _load_user(db: Session, profile: AuthUserProfile) -> User:
    user = get_user_by_id(db, UUID(profile.id))
    if user is None:
        raise ApiBusinessError("UNAUTHORIZED", "用户不存在或已失效", 401)
    return user


def _require_admin(
    user: Annotated[AuthUserProfile, Depends(get_current_user)],
) -> AuthUserProfile:
    codes = {code.lower() for code in user.roleCodes}
    if not (codes & _ADMIN_ROLES):
        raise ApiBusinessError("FORBIDDEN", "仅管理员可查看用量统计", 403)
    return user


@router.get("/api/v1/billing/plans", response_model=ApiResponse[list[BillingPlanDto]])
def get_billing_plans(
    _: Annotated[AuthUserProfile, Depends(get_current_user)],
):
    return success(list_plans())


@router.get("/api/v1/billing/me", response_model=ApiResponse[BillingMeDto])
def get_my_billing(
    user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(get_billing_me(db, _load_user(db, user)))


@router.get("/api/v1/billing/pay-options", response_model=ApiResponse[BillingPayOptionsDto])
def get_billing_pay_options(
    _: Annotated[AuthUserProfile, Depends(get_current_user)],
):
    return success(get_pay_options())


@router.post("/api/v1/billing/orders", response_model=ApiResponse[BillingOrderDto])
def post_billing_order(
    body: CreateBillingOrderBody,
    user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(create_order(db, _load_user(db, user), body.planCode), message="订单已创建")


@router.post(
    "/api/v1/billing/orders/{order_id}/stripe/checkout",
    response_model=ApiResponse[StripeCheckoutDto],
)
def post_stripe_checkout(
    order_id: UUID,
    user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(
        start_stripe_checkout(db, _load_user(db, user), order_id),
        message="请前往 Stripe 测试收银台完成支付",
    )


@router.get("/api/v1/billing/stripe/return")
def stripe_return(
    session_id: str = Query(default=""),
    db: Session = Depends(get_db),
):
    frontend = get_settings().frontend_base_url.rstrip("/")
    try:
        handle_stripe_return(db, session_id)
        return RedirectResponse(f"{frontend}/plans?pay=success", status_code=303)
    except ApiBusinessError:
        return RedirectResponse(f"{frontend}/plans?pay=failed", status_code=303)


@router.post(
    "/api/v1/billing/orders/{order_id}/alipay/page-pay",
    response_model=ApiResponse[AlipayPagePayDto],
)
def post_alipay_page_pay(
    order_id: UUID,
    user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(
        start_alipay_page_pay(db, _load_user(db, user), order_id),
        message="请前往支付宝沙箱收银台完成支付",
    )


@router.post(
    "/api/v1/billing/orders/{order_id}/mock-pay",
    response_model=ApiResponse[BillingOrderDto],
)
def post_mock_pay(
    order_id: UUID,
    user: Annotated[AuthUserProfile, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    return success(
        mock_pay_order(db, _load_user(db, user), order_id),
        message="支付成功，已升级为专业版",
    )


@router.get("/api/v1/billing/alipay/return")
def alipay_return(request: Request, db: Session = Depends(get_db)):
    frontend = get_settings().frontend_base_url.rstrip("/")
    try:
        handle_alipay_return(db, {key: str(value) for key, value in request.query_params.items()})
        return RedirectResponse(f"{frontend}/plans?pay=success", status_code=303)
    except ApiBusinessError:
        return RedirectResponse(f"{frontend}/plans?pay=failed", status_code=303)


@router.post("/api/v1/billing/alipay/notify")
async def alipay_notify(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    params = {str(key): str(value) for key, value in form.multi_items()}
    try:
        handle_alipay_notify(db, params)
        return PlainTextResponse("success")
    except Exception:
        return PlainTextResponse("fail")


@router.get("/api/v1/admin/usage-stats", response_model=ApiResponse[AdminUsageStatsDto])
def get_usage_stats(
    user: Annotated[AuthUserProfile, Depends(_require_admin)],
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
):
    scope = resolve_tenant_scope(user)
    tenant_id = None if scope.is_platform else scope.tenant_id
    return success(get_admin_usage_stats(db, days=days, tenant_id=tenant_id))
