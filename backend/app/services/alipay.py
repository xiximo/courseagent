from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, unquote_plus

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from app.api.errors import ApiBusinessError
from app.config import Settings

SANDBOX_GATEWAY = "https://openapi-sandbox.dl.alipaydev.com/gateway.do"
PROD_GATEWAY = "https://openapi.alipay.com/gateway.do"


def alipay_gateway(settings: Settings) -> str:
    custom = (settings.alipay_gateway or "").strip()
    if custom:
        return custom
    return SANDBOX_GATEWAY if settings.alipay_sandbox else PROD_GATEWAY


def alipay_ready(settings: Settings) -> bool:
    return bool(
        (settings.alipay_app_id or "").strip()
        and _resolve_key(
            settings.alipay_app_private_key,
            settings.alipay_app_private_key_path,
        )
        and _resolve_key(settings.alipay_public_key, settings.alipay_public_key_path)
    )


def require_alipay_ready(settings: Settings) -> None:
    if not alipay_ready(settings):
        raise ApiBusinessError(
            "ALIPAY_NOT_CONFIGURED",
            "未配置支付宝沙箱：请在 backend/.env 填写 ALIPAY_APP_ID、"
            "ALIPAY_APP_PRIVATE_KEY（或 PATH）与 ALIPAY_PUBLIC_KEY（或 PATH）",
            400,
        )


def build_page_pay_url(
    settings: Settings,
    *,
    out_trade_no: str,
    total_amount: str,
    subject: str,
) -> str:
    require_alipay_ready(settings)
    notify_url = (settings.alipay_notify_url or "").strip() or (
        f"{settings.public_base_url.rstrip('/')}/api/v1/billing/alipay/notify"
    )
    return_url = (settings.alipay_return_url or "").strip() or (
        f"{settings.public_base_url.rstrip('/')}/api/v1/billing/alipay/return"
    )
    params = {
        "app_id": settings.alipay_app_id.strip(),
        "method": "alipay.trade.page.pay",
        "format": "JSON",
        "charset": "utf-8",
        "sign_type": "RSA2",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": notify_url,
        "return_url": return_url,
        "biz_content": json.dumps(
            {
                "out_trade_no": out_trade_no,
                "product_code": "FAST_INSTANT_TRADE_PAY",
                "total_amount": total_amount,
                "subject": subject,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    params["sign"] = sign_rsa2(params, load_private_key(settings))
    query = "&".join(
        f"{quote_plus(key)}={quote_plus(value)}" for key, value in params.items()
    )
    return f"{alipay_gateway(settings)}?{query}"


def verify_alipay_params(settings: Settings, params: dict[str, str]) -> bool:
    sign = params.get("sign")
    if not sign:
        return False
    unsigned = {
        key: _maybe_unquote(value)
        for key, value in params.items()
        if key not in {"sign", "sign_type"} and value not in (None, "")
    }
    message = sign_content(unsigned)
    try:
        public_key = load_public_key(settings)
        public_key.verify(
            base64.b64decode(sign),
            message.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def sign_rsa2(params: dict[str, str], private_key: RSAPrivateKey) -> str:
    signature = private_key.sign(
        sign_content(params).encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def sign_content(params: dict[str, str]) -> str:
    items = [
        (key, value)
        for key, value in params.items()
        if key not in {"sign"} and value not in (None, "")
    ]
    items.sort(key=lambda item: item[0])
    return "&".join(f"{key}={value}" for key, value in items)


def load_private_key(settings: Settings) -> RSAPrivateKey:
    pem = _normalize_private_pem(
        _resolve_key(settings.alipay_app_private_key, settings.alipay_app_private_key_path)
    )
    key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise ApiBusinessError("ALIPAY_KEY_INVALID", "支付宝应用私钥无效", 400)
    return key


def load_public_key(settings: Settings) -> RSAPublicKey:
    pem = _normalize_public_pem(
        _resolve_key(settings.alipay_public_key, settings.alipay_public_key_path)
    )
    key = serialization.load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(key, RSAPublicKey):
        raise ApiBusinessError("ALIPAY_KEY_INVALID", "支付宝公钥无效", 400)
    return key


def _resolve_key(raw: str, path: str) -> str:
    file_path = (path or "").strip()
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    return (raw or "").replace("\\n", "\n").strip()


def _normalize_private_pem(value: str) -> str:
    text = value.strip()
    if "BEGIN" in text:
        return text
    return (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        f"{_wrap_b64(text)}\n"
        "-----END RSA PRIVATE KEY-----"
    )


def _normalize_public_pem(value: str) -> str:
    text = value.strip()
    if "BEGIN" in text:
        return text
    return (
        "-----BEGIN PUBLIC KEY-----\n"
        f"{_wrap_b64(text)}\n"
        "-----END PUBLIC KEY-----"
    )


def _wrap_b64(value: str) -> str:
    compact = "".join(value.split())
    return "\n".join(compact[i : i + 64] for i in range(0, len(compact), 64))


def _maybe_unquote(value: str) -> str:
    if not value:
        return value
    if "%" in value:
        try:
            return unquote_plus(value)
        except Exception:
            return value
    return value
