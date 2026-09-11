from datetime import datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.services.alipay import (
    SANDBOX_GATEWAY,
    alipay_ready,
    build_page_pay_url,
    sign_content,
    sign_rsa2,
    verify_alipay_params,
)


def _settings_with_keys() -> Settings:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return Settings(
        _env_file=None,
        alipay_sandbox=True,
        alipay_app_id="9021000000000000",
        alipay_app_private_key=private_pem,
        alipay_public_key=public_pem,
        public_base_url="http://127.0.0.1:8080",
        frontend_base_url="http://localhost:5173",
    )


def test_sign_and_verify_roundtrip():
    settings = _settings_with_keys()
    from app.services.alipay import load_private_key

    # 支付宝回跳验签会去掉 sign / sign_type，与官方通知一致
    payload = {
        "app_id": settings.alipay_app_id,
        "out_trade_no": "abc123",
        "total_amount": "199.00",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    params = {
        **payload,
        "sign_type": "RSA2",
        "sign": sign_rsa2(payload, load_private_key(settings)),
    }
    assert verify_alipay_params(settings, params)


def test_verify_rejects_tampered_amount():
    settings = _settings_with_keys()
    from app.services.alipay import load_private_key

    params = {"out_trade_no": "abc123", "total_amount": "199.00"}
    params["sign"] = sign_rsa2(params, load_private_key(settings))
    params["total_amount"] = "1.00"
    assert not verify_alipay_params(settings, params)


def test_page_pay_url_uses_sandbox_gateway():
    settings = _settings_with_keys()
    url = build_page_pay_url(
        settings,
        out_trade_no="a" * 32,
        total_amount="199.00",
        subject="启明顾问专业版",
    )
    assert url.startswith(SANDBOX_GATEWAY + "?")
    assert "alipay.trade.page.pay" in url
    assert "FAST_INSTANT_TRADE_PAY" in url
    assert "sign=" in url


def test_alipay_ready_requires_keys():
    assert not alipay_ready(Settings(_env_file=None, alipay_app_id="123"))
    assert alipay_ready(_settings_with_keys())


def test_sign_content_skips_sign_and_sorts():
    assert (
        sign_content({"b": "2", "a": "1", "sign": "x"})
        == "a=1&b=2"
    )
