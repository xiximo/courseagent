from app.services.login_audit import resolve_client_ip


class _Client:
    def __init__(self, host: str | None):
        self.host = host


class _Request:
    def __init__(
        self,
        headers: dict[str, str] | None = None,
        host: str | None = None,
    ):
        self.headers = headers or {}
        self.client = _Client(host) if host is not None else None


def test_resolve_client_ip_prefers_forwarded_for():
    request = _Request(
        headers={"x-forwarded-for": "203.0.113.10, 10.0.0.1"},
        host="127.0.0.1",
    )
    assert resolve_client_ip(request) == "203.0.113.10"


def test_resolve_client_ip_falls_back_to_real_ip():
    request = _Request(headers={"x-real-ip": "198.51.100.2"}, host="127.0.0.1")
    assert resolve_client_ip(request) == "198.51.100.2"


def test_resolve_client_ip_uses_peer_host():
    request = _Request(host="192.168.1.8")
    assert resolve_client_ip(request) == "192.168.1.8"


def test_resolve_client_ip_empty_when_missing():
    request = _Request()
    assert resolve_client_ip(request) == ""
