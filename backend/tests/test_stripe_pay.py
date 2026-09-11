from app.config import Settings
from app.services.billing import handle_stripe_return
from app.services.stripe_pay import (
    session_is_paid,
    session_order_id,
    stripe_mode,
    stripe_ready,
)


def test_stripe_ready_and_mode():
    assert not stripe_ready(Settings(_env_file=None, stripe_secret_key=""))
    assert stripe_ready(Settings(_env_file=None, stripe_secret_key="sk_test_abc"))
    assert stripe_mode(Settings(_env_file=None, stripe_secret_key="sk_test_abc")) == "test"
    assert stripe_mode(Settings(_env_file=None, stripe_secret_key="sk_live_abc")) == "live"


def test_session_paid_and_order_id():
    session = {
        "id": "cs_test_1",
        "status": "complete",
        "payment_status": "paid",
        "client_reference_id": "fallback-id",
        "metadata": {"order_id": "11111111-1111-1111-1111-111111111111"},
    }
    assert session_is_paid(session)
    assert session_order_id(session) == "11111111-1111-1111-1111-111111111111"
    assert not session_is_paid({"status": "open", "payment_status": "unpaid"})


def test_handle_stripe_return_rejects_unpaid(monkeypatch):
    settings = Settings(_env_file=None, stripe_secret_key="sk_test_abc")

    def _fake_retrieve(_settings, _session_id):
        return {"status": "open", "payment_status": "unpaid", "metadata": {}}

    monkeypatch.setattr(
        "app.services.billing.retrieve_checkout_session", _fake_retrieve
    )
    try:
        handle_stripe_return(None, "cs_test_1", settings=settings)  # type: ignore[arg-type]
        raise AssertionError("expected unpaid session to fail")
    except Exception as exc:
        assert getattr(exc, "code", "") == "STRIPE_UNPAID"
