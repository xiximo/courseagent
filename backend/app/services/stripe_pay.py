from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

from app.api.errors import ApiBusinessError
from app.config import Settings

STRIPE_API = "https://api.stripe.com/v1"


def stripe_ready(settings: Settings) -> bool:
    return bool((settings.stripe_secret_key or "").strip())


def require_stripe_ready(settings: Settings) -> None:
    if not stripe_ready(settings):
        raise ApiBusinessError(
            "STRIPE_NOT_CONFIGURED",
            "未配置 Stripe：请在 backend/.env 填写 STRIPE_SECRET_KEY（测试模式 sk_test_）",
            400,
        )


def stripe_mode(settings: Settings) -> str:
    key = (settings.stripe_secret_key or "").strip()
    if key.startswith("sk_live_"):
        return "live"
    if key.startswith("sk_test_"):
        return "test"
    return "unknown"


def create_checkout_session(
    settings: Settings,
    *,
    order_id: str,
    amount_cents: int,
    currency: str,
    product_name: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    require_stripe_ready(settings)
    payload = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": order_id,
        "metadata[order_id]": order_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": currency,
        "line_items[0][price_data][unit_amount]": str(amount_cents),
        "line_items[0][price_data][product_data][name]": product_name,
    }
    return _request(settings, "POST", "/checkout/sessions", payload)


def retrieve_checkout_session(settings: Settings, session_id: str) -> dict[str, Any]:
    require_stripe_ready(settings)
    sid = (session_id or "").strip()
    if not sid:
        raise ApiBusinessError("STRIPE_SESSION_INVALID", "缺少 Stripe Checkout Session", 400)
    return _request(settings, "GET", f"/checkout/sessions/{sid}")


def session_is_paid(session: dict[str, Any]) -> bool:
    status = str(session.get("status") or "")
    payment = str(session.get("payment_status") or "")
    return status == "complete" and payment == "paid"


def session_order_id(session: dict[str, Any]) -> str:
    metadata = session.get("metadata") or {}
    if isinstance(metadata, dict):
        raw = str(metadata.get("order_id") or "").strip()
        if raw:
            return raw
    return str(session.get("client_reference_id") or "").strip()


def _request(
    settings: Settings, method: str, path: str, data: dict[str, str] | None = None
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {settings.stripe_secret_key.strip()}",
        "Stripe-Version": "2024-06-20",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.request(
                method,
                f"{STRIPE_API}{path}",
                headers=headers,
                content=urlencode(data) if data else None,
            )
    except httpx.HTTPError as exc:
        raise ApiBusinessError("STRIPE_NETWORK", f"调用 Stripe 失败：{exc}", 502) from exc
    body: Any
    try:
        body = response.json()
    except ValueError as exc:
        raise ApiBusinessError("STRIPE_BAD_RESPONSE", "Stripe 返回无法解析", 502) from exc
    if response.status_code >= 400:
        error = body.get("error") if isinstance(body, dict) else None
        message = (
            error.get("message")
            if isinstance(error, dict) and error.get("message")
            else f"Stripe 错误 HTTP {response.status_code}"
        )
        raise ApiBusinessError("STRIPE_API_ERROR", str(message), 400)
    if not isinstance(body, dict):
        raise ApiBusinessError("STRIPE_BAD_RESPONSE", "Stripe 返回格式异常", 502)
    return body
