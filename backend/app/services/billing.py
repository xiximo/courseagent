from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.errors import ApiBusinessError
from app.config import Settings, get_settings
from app.services.tenant_scope import is_platform_user
from app.db.models.billing import BillingOrderRecord
from app.db.models.tenant import TenantRecord
from app.services.alipay import (
    alipay_gateway,
    alipay_ready,
    build_page_pay_url,
    require_alipay_ready,
    verify_alipay_params,
)
from app.db.models.course_agent import CourseAgentMessageRecord, CourseAgentRecord, CourseAgentSessionRecord
from app.db.models.course_agent_resources import CourseAgentKnowledgeBaseRecord
from app.db.models.user import User
from app.schemas.billing import (
    AdminUsageStatsDto,
    AlipayPagePayDto,
    BillingMeDto,
    BillingOrderDto,
    BillingPayOptionsDto,
    BillingPlanDto,
    BillingUsageDto,
    StripeCheckoutDto,
    UsageTrendPointDto,
    UsageUserRankDto,
)
from app.services.stripe_pay import (
    create_checkout_session,
    retrieve_checkout_session,
    session_is_paid,
    session_order_id,
    stripe_mode,
    stripe_ready,
)

PLAN_FREE = "free"
PLAN_PRO = "pro"
FREE_CHAT_LIMIT = 50
FREE_KNOWLEDGE_BASE_LIMIT = 1
QUOTA_EXCEEDED_MESSAGE = "已用完，请升级"
KNOWLEDGE_BASE_LIMIT_MESSAGE = "免费版仅可创建 1 个知识库，请升级专业版"

PLANS: dict[str, BillingPlanDto] = {
    PLAN_FREE: BillingPlanDto(
        code=PLAN_FREE,
        name="免费版",
        priceLabel="¥0 / 月",
        priceCents=0,
        chatLimit=FREE_CHAT_LIMIT,
        knowledgeBaseLimit=FREE_KNOWLEDGE_BASE_LIMIT,
        features=[
            "每月 50 次课程咨询对话",
            "1 个知识库与顾问配置",
            "基础型 Agent",
        ],
    ),
    PLAN_PRO: BillingPlanDto(
        code=PLAN_PRO,
        name="专业版",
        priceLabel="¥199 / 月",
        priceCents=19900,
        chatLimit=None,
        knowledgeBaseLimit=None,
        highlighted=True,
        features=[
            "无限对话次数",
            "不限数量知识库与顾问配置",
            "基础型 Agent + Harness Agent",
            "知识库检索与工具编排",
        ],
    ),
}


def list_plans() -> list[BillingPlanDto]:
    return [PLANS[PLAN_FREE], PLANS[PLAN_PRO]]


def current_year_month(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    return f"{moment.year:04d}-{moment.month:02d}"


def normalize_plan(plan_code: str | None) -> str:
    code = (plan_code or PLAN_FREE).strip().lower()
    return PLAN_PRO if code == PLAN_PRO else PLAN_FREE


def load_tenant(db: Session | None, tenant_id: UUID | None) -> TenantRecord | None:
    if db is None or tenant_id is None:
        return None
    return db.get(TenantRecord, tenant_id)


def resolve_plan_code(
    user: User | None,
    db: Session | None = None,
    tenant: TenantRecord | None = None,
) -> str:
    if user is not None and is_platform_user(getattr(user, "role_codes", None)):
        return PLAN_PRO
    row = tenant
    if row is None and user is not None:
        row = load_tenant(db, getattr(user, "tenant_id", None))
    if row is not None:
        return normalize_plan(getattr(row, "plan_code", None))
    return normalize_plan(getattr(user, "plan_code", None) if user else None)


def is_pro_plan(user: User | None, db: Session | None = None) -> bool:
    return resolve_plan_code(user, db=db) == PLAN_PRO


def tenant_has_pro(db: Session, tenant_id: UUID) -> bool:
    tenant = load_tenant(db, tenant_id)
    return tenant is not None and normalize_plan(tenant.plan_code) == PLAN_PRO


def require_pro_plan(user: User | None, db: Session | None = None) -> None:
    if not is_pro_plan(user, db=db):
        raise ApiBusinessError(
            "PLAN_REQUIRED",
            "Harness Agent 为专业版功能，请先升级套餐",
            403,
        )


def is_harness_agent_type(agent_type: str | None) -> bool:
    return (agent_type or "workflow") != "basic"


def require_agent_type_for_plan(
    user: User | None, db: Session | None, agent_type: str | None
) -> None:
    if not is_harness_agent_type(agent_type):
        return
    if user is not None and is_platform_user(getattr(user, "role_codes", None)):
        return
    require_pro_plan(user, db=db)


def count_tenant_knowledge_bases(db: Session, tenant_id: UUID | None) -> int:
    stmt = select(func.count()).select_from(CourseAgentKnowledgeBaseRecord)
    if tenant_id is not None:
        stmt = stmt.where(CourseAgentKnowledgeBaseRecord.tenant_id == tenant_id)
    else:
        stmt = stmt.where(CourseAgentKnowledgeBaseRecord.tenant_id.is_(None))
    return int(db.scalar(stmt) or 0)


def require_knowledge_base_quota(
    db: Session | None,
    user: User | None,
    *,
    used: int | None = None,
) -> None:
    if user is not None and is_platform_user(getattr(user, "role_codes", None)):
        return
    if is_pro_plan(user, db=db):
        return
    current = used
    if current is None:
        if db is None or user is None:
            current = 0
        else:
            current = count_tenant_knowledge_bases(db, getattr(user, "tenant_id", None))
    if current >= FREE_KNOWLEDGE_BASE_LIMIT:
        raise ApiBusinessError("PLAN_REQUIRED", KNOWLEDGE_BASE_LIMIT_MESSAGE, 403)


def tenant_month_used(tenant: TenantRecord, year_month: str) -> int:
    if getattr(tenant, "usage_year_month", None) != year_month:
        return 0
    return int(getattr(tenant, "chat_count", 0) or 0)


def apply_tenant_chat_quota(tenant: TenantRecord, *, year_month: str | None = None) -> int:
    month = year_month or current_year_month()
    used = tenant_month_used(tenant, month)
    if normalize_plan(getattr(tenant, "plan_code", None)) != PLAN_PRO and used >= FREE_CHAT_LIMIT:
        raise ApiBusinessError("QUOTA_EXCEEDED", QUOTA_EXCEEDED_MESSAGE, 402)
    tenant.usage_year_month = month
    tenant.chat_count = used + 1
    return int(tenant.chat_count)


def consume_chat_quota(db: Session, user: User | None, *, is_preview: bool) -> None:
    if is_preview or user is None:
        return
    if is_platform_user(getattr(user, "role_codes", None)):
        return
    tenant = load_tenant(db, getattr(user, "tenant_id", None))
    if tenant is None:
        return
    apply_tenant_chat_quota(tenant)
    db.flush()


def to_order_dto(row: BillingOrderRecord) -> BillingOrderDto:
    return BillingOrderDto(
        id=str(row.id),
        planCode=row.plan_code,
        amountCents=row.amount_cents,
        status=row.status,
        channel=getattr(row, "channel", None) or "alipay",
        providerTradeNo=getattr(row, "provider_trade_no", None),
        createdAt=row.created_at.isoformat() if row.created_at else "",
        paidAt=row.paid_at.isoformat() if row.paid_at else None,
    )


def get_pay_options(settings: Settings | None = None) -> BillingPayOptionsDto:
    env = settings or get_settings()
    return BillingPayOptionsDto(
        alipaySandbox=bool(env.alipay_sandbox),
        alipayReady=alipay_ready(env),
        mockPayEnabled=bool(env.alipay_allow_mock),
        gateway=alipay_gateway(env),
        stripeReady=stripe_ready(env),
        stripeMode=stripe_mode(env),
        stripeCurrency=(env.stripe_currency or "cny").strip().lower() or "cny",
    )


def get_billing_me(db: Session, user: User) -> BillingMeDto:
    tenant_id = getattr(user, "tenant_id", None)
    tenant = load_tenant(db, tenant_id)
    platform = is_platform_user(getattr(user, "role_codes", None))
    month = current_year_month()
    if platform:
        plan_code = PLAN_PRO
        used = 0
        upgraded = None
    elif tenant is not None:
        plan_code = normalize_plan(tenant.plan_code)
        used = tenant_month_used(tenant, month)
        upgraded = getattr(tenant, "plan_upgraded_at", None)
    else:
        plan_code = PLAN_FREE
        used = 0
        upgraded = None
    plan = PLANS[plan_code]
    limit = plan.chatLimit
    remaining = None if limit is None else max(0, limit - used)
    kb_limit = None if platform or plan_code == PLAN_PRO else plan.knowledgeBaseLimit
    kb_used = 0 if platform else count_tenant_knowledge_bases(db, tenant_id)
    return BillingMeDto(
        planCode=plan_code,
        planName=plan.name,
        planUpgradedAt=upgraded.isoformat() if upgraded else None,
        usage=BillingUsageDto(
            yearMonth=month,
            used=used,
            limit=limit,
            remaining=remaining,
        ),
        canManageKnowledge=True,
        canUseHarnessAgent=plan_code == PLAN_PRO,
        knowledgeBaseLimit=kb_limit,
        knowledgeBaseUsed=kb_used,
        canCreateKnowledgeBase=kb_limit is None or kb_used < kb_limit,
    )


def create_order(db: Session, user: User, plan_code: str) -> BillingOrderDto:
    code = normalize_plan(plan_code)
    if code != PLAN_PRO:
        raise ApiBusinessError("INVALID_PLAN", "当前仅支持升级到专业版", 400)
    if is_pro_plan(user, db=db):
        raise ApiBusinessError("ALREADY_PRO", "您已是专业版，无需重复购买", 400)
    plan = PLANS[PLAN_PRO]
    env = get_settings()
    channel = "stripe" if stripe_ready(env) else "alipay"
    row = BillingOrderRecord(
        user_id=user.id,
        plan_code=PLAN_PRO,
        amount_cents=plan.priceCents,
        channel=channel,
        status="pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return to_order_dto(row)


def mock_pay_order(db: Session, user: User, order_id: UUID) -> BillingOrderDto:
    if not get_settings().alipay_allow_mock:
        raise ApiBusinessError("MOCK_PAY_DISABLED", "已关闭本地模拟支付，请使用 Stripe 测试支付", 400)
    row = db.get(BillingOrderRecord, order_id)
    if row is None or row.user_id != user.id:
        raise ApiBusinessError("NOT_FOUND", "订单不存在", 404)
    return to_order_dto(fulfill_paid_order(db, row, channel="mock"))


def start_stripe_checkout(
    db: Session, user: User, order_id: UUID, settings: Settings | None = None
) -> StripeCheckoutDto:
    env = settings or get_settings()
    row = db.get(BillingOrderRecord, order_id)
    if row is None or row.user_id != user.id:
        raise ApiBusinessError("NOT_FOUND", "订单不存在", 404)
    if row.status == "paid":
        raise ApiBusinessError("ALREADY_PAID", "订单已支付", 400)
    row.channel = "stripe"
    db.commit()
    db.refresh(row)
    success_url = (
        f"{env.public_base_url.rstrip('/')}/api/v1/billing/stripe/return"
        "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = f"{env.frontend_base_url.rstrip('/')}/plans?pay=canceled"
    currency = (env.stripe_currency or "cny").strip().lower() or "cny"
    try:
        session = create_checkout_session(
            env,
            order_id=str(row.id),
            amount_cents=int(row.amount_cents or 0),
            currency=currency,
            product_name="启明顾问专业版",
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ApiBusinessError as exc:
        if currency != "usd" and exc.code == "STRIPE_API_ERROR":
            session = create_checkout_session(
                env,
                order_id=str(row.id),
                amount_cents=int(row.amount_cents or 0),
                currency="usd",
                product_name="Qiming Advisor Pro",
                success_url=success_url,
                cancel_url=cancel_url,
            )
        else:
            raise
    pay_url = str(session.get("url") or "").strip()
    session_id = str(session.get("id") or "").strip()
    if not pay_url or not session_id:
        raise ApiBusinessError("STRIPE_BAD_RESPONSE", "Stripe 未返回收银台地址", 502)
    return StripeCheckoutDto(
        orderId=str(row.id),
        payUrl=pay_url,
        sessionId=session_id,
        mode=stripe_mode(env),
    )


def handle_stripe_return(
    db: Session, session_id: str, settings: Settings | None = None
) -> BillingOrderRecord:
    env = settings or get_settings()
    session = retrieve_checkout_session(env, session_id)
    if not session_is_paid(session):
        raise ApiBusinessError("STRIPE_UNPAID", "Stripe 订单未支付成功", 400)
    order_id = session_order_id(session)
    row = _get_order_by_out_trade_no(db, order_id)
    if row is None:
        raise ApiBusinessError("NOT_FOUND", "订单不存在", 404)
    return fulfill_paid_order(
        db,
        row,
        channel="stripe",
        provider_trade_no=str(session.get("payment_intent") or session.get("id") or ""),
    )


def start_alipay_page_pay(
    db: Session, user: User, order_id: UUID, settings: Settings | None = None
) -> AlipayPagePayDto:
    env = settings or get_settings()
    require_alipay_ready(env)
    row = db.get(BillingOrderRecord, order_id)
    if row is None or row.user_id != user.id:
        raise ApiBusinessError("NOT_FOUND", "订单不存在", 404)
    if row.status == "paid":
        raise ApiBusinessError("ALREADY_PAID", "订单已支付", 400)
    row.channel = "alipay"
    db.commit()
    db.refresh(row)
    amount = f"{(row.amount_cents or 0) / 100:.2f}"
    pay_url = build_page_pay_url(
        env,
        out_trade_no=row.id.hex,
        total_amount=amount,
        subject="启明顾问专业版",
    )
    return AlipayPagePayDto(
        orderId=str(row.id),
        payUrl=pay_url,
        gateway=alipay_gateway(env),
    )


def handle_alipay_callback(
    db: Session,
    params: dict[str, str],
    *,
    settings: Settings | None = None,
    require_trade_success: bool = False,
) -> BillingOrderRecord:
    env = settings or get_settings()
    require_alipay_ready(env)
    if not verify_alipay_params(env, params):
        raise ApiBusinessError("ALIPAY_SIGN_INVALID", "支付宝验签失败", 400)
    out_trade_no = (params.get("out_trade_no") or "").strip()
    trade_status = (params.get("trade_status") or "").strip()
    if require_trade_success and trade_status not in {"TRADE_SUCCESS", "TRADE_FINISHED"}:
        raise ApiBusinessError("ALIPAY_UNPAID", "支付宝订单未支付成功", 400)
    row = _get_order_by_out_trade_no(db, out_trade_no)
    if row is None:
        raise ApiBusinessError("NOT_FOUND", "订单不存在", 404)
    return fulfill_paid_order(
        db,
        row,
        channel="alipay",
        provider_trade_no=(params.get("trade_no") or "").strip() or None,
    )


def handle_alipay_return(db: Session, params: dict[str, str]) -> BillingOrderRecord:
    # 同步回跳通常带签名；本地无法收异步通知时以此履约。
    return handle_alipay_callback(db, params, require_trade_success=False)


def handle_alipay_notify(db: Session, params: dict[str, str]) -> BillingOrderRecord:
    return handle_alipay_callback(db, params, require_trade_success=True)


def fulfill_paid_order(
    db: Session,
    row: BillingOrderRecord,
    *,
    channel: str,
    provider_trade_no: str | None = None,
) -> BillingOrderRecord:
    if provider_trade_no:
        row.provider_trade_no = provider_trade_no
    row.channel = channel
    if row.status == "paid":
        db.commit()
        db.refresh(row)
        return row
    paid_at = datetime.now(UTC)
    row.status = "paid"
    row.paid_at = paid_at
    user = db.get(User, row.user_id)
    if user is not None:
        tenant = load_tenant(db, getattr(user, "tenant_id", None))
        if tenant is not None:
            tenant.plan_code = PLAN_PRO
            tenant.plan_upgraded_at = paid_at
        else:
            user.plan_code = PLAN_PRO
            user.plan_upgraded_at = paid_at
    db.commit()
    db.refresh(row)
    return row


def _get_order_by_out_trade_no(db: Session, out_trade_no: str) -> BillingOrderRecord | None:
    raw = (out_trade_no or "").strip()
    if not raw:
        return None
    try:
        return db.get(BillingOrderRecord, UUID(raw))
    except ValueError:
        return None


def _day_start(days: int) -> datetime:
    today = datetime.now(UTC).date()
    start = today - timedelta(days=days - 1)
    return datetime(start.year, start.month, start.day, tzinfo=UTC)


def get_admin_usage_stats(
    db: Session, *, days: int = 30, tenant_id: UUID | None = None
) -> AdminUsageStatsDto:
    window = max(7, min(days, 90))
    start = _day_start(window)
    tenant_agent_ids = None
    tenant_users_stmt = None
    if tenant_id is not None:
        tenant_agent_ids = select(CourseAgentRecord.agent_id).where(
            CourseAgentRecord.tenant_id == tenant_id
        )
        tenant_users_stmt = select(User.id).where(User.tenant_id == tenant_id)

    chat_stmt = select(func.count(CourseAgentMessageRecord.id)).where(
        CourseAgentMessageRecord.role == "user"
    )
    if tenant_id is not None:
        chat_stmt = chat_stmt.join(
            CourseAgentSessionRecord,
            CourseAgentSessionRecord.id == CourseAgentMessageRecord.session_id,
        ).where(
            or_(
                CourseAgentSessionRecord.agent_id.in_(tenant_agent_ids),
                CourseAgentSessionRecord.user_id.in_(tenant_users_stmt),
            )
        )
    total_chats = int(db.scalar(chat_stmt) or 0)

    active_stmt = select(func.count(func.distinct(CourseAgentSessionRecord.user_id))).where(
        CourseAgentSessionRecord.user_id.is_not(None),
        CourseAgentSessionRecord.updated_at >= start,
    )
    if tenant_id is not None:
        active_stmt = active_stmt.where(
            or_(
                CourseAgentSessionRecord.agent_id.in_(tenant_agent_ids),
                CourseAgentSessionRecord.user_id.in_(tenant_users_stmt),
            )
        )
    active_users = int(db.scalar(active_stmt) or 0)

    free_stmt = (
        select(func.count(TenantRecord.id))
        .select_from(TenantRecord)
        .where(TenantRecord.plan_code != PLAN_PRO)
    )
    pro_stmt = (
        select(func.count(TenantRecord.id))
        .select_from(TenantRecord)
        .where(TenantRecord.plan_code == PLAN_PRO)
    )
    if tenant_id is not None:
        free_stmt = free_stmt.where(TenantRecord.id == tenant_id)
        pro_stmt = pro_stmt.where(TenantRecord.id == tenant_id)
    free_users = int(db.scalar(free_stmt) or 0)
    pro_users = int(db.scalar(pro_stmt) or 0)

    day_expr = func.date_trunc("day", CourseAgentMessageRecord.created_at)
    chat_trend_stmt = (
        select(day_expr, func.count(CourseAgentMessageRecord.id))
        .where(
            CourseAgentMessageRecord.role == "user",
            CourseAgentMessageRecord.created_at >= start,
        )
        .group_by(day_expr)
        .order_by(day_expr)
    )
    if tenant_id is not None:
        chat_trend_stmt = chat_trend_stmt.join(
            CourseAgentSessionRecord,
            CourseAgentSessionRecord.id == CourseAgentMessageRecord.session_id,
        ).where(
            or_(
                CourseAgentSessionRecord.agent_id.in_(tenant_agent_ids),
                CourseAgentSessionRecord.user_id.in_(tenant_users_stmt),
            )
        )
    chat_rows = db.execute(chat_trend_stmt).all()
    chat_map = {_as_date(key): int(count) for key, count in chat_rows}

    user_day = func.date_trunc("day", CourseAgentSessionRecord.updated_at)
    user_trend_stmt = (
        select(user_day, func.count(func.distinct(CourseAgentSessionRecord.user_id)))
        .where(
            CourseAgentSessionRecord.user_id.is_not(None),
            CourseAgentSessionRecord.updated_at >= start,
        )
        .group_by(user_day)
        .order_by(user_day)
    )
    if tenant_id is not None:
        user_trend_stmt = user_trend_stmt.where(
            or_(
                CourseAgentSessionRecord.agent_id.in_(tenant_agent_ids),
                CourseAgentSessionRecord.user_id.in_(tenant_users_stmt),
            )
        )
    user_rows = db.execute(user_trend_stmt).all()
    user_map = {_as_date(key): int(count) for key, count in user_rows}

    trend: list[UsageTrendPointDto] = []
    cursor = start.date()
    today = datetime.now(UTC).date()
    while cursor <= today:
        key = cursor.isoformat()
        trend.append(
            UsageTrendPointDto(
                date=key,
                chatCount=chat_map.get(key, 0),
                activeUsers=user_map.get(key, 0),
            )
        )
        cursor += timedelta(days=1)

    rank_stmt = (
        select(
            User.id,
            User.username,
            User.full_name,
            func.count(CourseAgentMessageRecord.id).label("chat_count"),
        )
        .select_from(CourseAgentMessageRecord)
        .join(
            CourseAgentSessionRecord,
            CourseAgentSessionRecord.id == CourseAgentMessageRecord.session_id,
        )
        .join(User, User.id == CourseAgentSessionRecord.user_id)
        .where(CourseAgentMessageRecord.role == "user")
    )
    if tenant_id is not None:
        rank_stmt = rank_stmt.where(
            or_(
                CourseAgentSessionRecord.agent_id.in_(tenant_agent_ids),
                CourseAgentSessionRecord.user_id.in_(tenant_users_stmt),
            )
        )
    rank_stmt = (
        rank_stmt.group_by(User.id, User.username, User.full_name)
        .order_by(func.count(CourseAgentMessageRecord.id).desc())
        .limit(10)
    )
    top_users = [
        UsageUserRankDto(
            userId=str(user_id),
            username=str(username or ""),
            fullName=str(full_name or username or "未命名"),
            chatCount=int(chat_count or 0),
        )
        for user_id, username, full_name, chat_count in db.execute(rank_stmt).all()
    ]

    return AdminUsageStatsDto(
        totalChats=total_chats,
        activeUsers=active_users,
        freeUsers=free_users,
        proUsers=pro_users,
        trend=trend,
        topUsers=top_users,
    )


def _as_date(value: object) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]
