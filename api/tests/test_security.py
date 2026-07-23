"""Тестове за пласта на сигурността на публичното API (режим C)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from api.security.config import SecurityConfig  # noqa: E402
from api.security.middleware import install_security  # noqa: E402
from api.security.net import client_ip  # noqa: E402
from api.security.ratelimit import InMemoryRateLimiter  # noqa: E402
from api.security.validation import validate_identifier  # noqa: E402


def _app(config: SecurityConfig, *, limiter: InMemoryRateLimiter | None = None) -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("вътрешна тайна, не бива да изтича")

    install_security(app, config, rate_limiter=limiter)
    return app


# --- Защитни хедъри -------------------------------------------------------------------


def test_security_headers_present(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_hsts_configurable() -> None:
    app = _app(SecurityConfig(rate_limit_enabled=False, hsts_enabled=True, hsts_max_age=100))
    with TestClient(app) as c:
        assert "max-age=100" in c.get("/ping").headers["Strict-Transport-Security"]
    app2 = _app(SecurityConfig(rate_limit_enabled=False, hsts_enabled=False))
    with TestClient(app2) as c:
        assert "Strict-Transport-Security" not in c.get("/ping").headers


# --- Валидация на идентификатор (обхождане на пътища) ---------------------------------


@pytest.mark.parametrize("bad", ["../etc", "a/b", "ALPHA", "-lead", "трудно", "x" * 101, ""])
def test_invalid_identifier_rejected(bad: str) -> None:
    with pytest.raises(HTTPException):
        validate_identifier(bad)


@pytest.mark.parametrize("good", ["alpha", "deynosti-kp-nzok-2025", "x", "a1-b2-c3"])
def test_valid_identifier_accepted(good: str) -> None:
    assert validate_identifier(good) == good


def test_traversal_identifier_returns_400(client: TestClient) -> None:
    assert client.get("/v1/datasets/..%2f..%2fetc").status_code in (400, 404)
    assert client.get("/v1/datasets/Alpha").status_code == 400


# --- Ограничаване на честотата --------------------------------------------------------


def test_in_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter(limit=2, window_seconds=60)
    assert limiter.hit("ip")[0] is True
    assert limiter.hit("ip")[0] is True
    allowed, retry_after = limiter.hit("ip")
    assert allowed is False
    assert retry_after > 0
    # Друг ключ не е засегнат.
    assert limiter.hit("other")[0] is True


def test_rate_limit_middleware_returns_429() -> None:
    cfg = SecurityConfig(
        rate_limit_enabled=True, rate_limit_requests=2, rate_limit_window_seconds=60
    )
    app = _app(cfg, limiter=InMemoryRateLimiter(2, 60))
    with TestClient(app) as c:
        assert c.get("/ping").status_code == 200
        assert c.get("/ping").status_code == 200
        blocked = c.get("/ping")
        assert blocked.status_code == 429
        assert "Retry-After" in blocked.headers


def test_health_is_exempt_from_rate_limit(client: TestClient) -> None:
    # Дори при много заявки, health не се лимитира (проверка на живост).
    for _ in range(5):
        assert client.get("/v1/health").status_code == 200


# --- Лимит за размер на тялото --------------------------------------------------------


def test_body_too_large_rejected() -> None:
    cfg = SecurityConfig(rate_limit_enabled=False, max_body_bytes=16)
    app = _app(cfg)
    with TestClient(app) as c:
        r = c.request("GET", "/ping", content=b"x" * 64)
        assert r.status_code == 413


# --- Безопасно обработване на грешки --------------------------------------------------


def test_internal_error_does_not_leak() -> None:
    cfg = SecurityConfig(rate_limit_enabled=False)
    app = _app(cfg)
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
        assert r.status_code == 500
        body = r.json()
        assert body["error"] == "internal_error"
        assert "correlation_id" in body
        assert "тайна" not in r.text


# --- CORS -----------------------------------------------------------------------------


def test_cors_allow_all_preflight() -> None:
    cfg = SecurityConfig(rate_limit_enabled=False, cors_allow_all=True)
    app = _app(cfg)
    with TestClient(app) as c:
        r = c.options(
            "/ping",
            headers={
                "Origin": "https://example.org",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.headers.get("access-control-allow-origin") == "*"


# --- Клиентски IP при доверени проксита -----------------------------------------------


def _request(headers: dict[str, str], peer: str) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (peer, 12345),
    }
    return Request(scope)


def test_client_ip_ignores_xff_without_trusted_hops() -> None:
    req = _request({"x-forwarded-for": "1.2.3.4"}, peer="10.0.0.1")
    assert client_ip(req, trusted_proxy_hops=0) == "10.0.0.1"


def test_client_ip_uses_trusted_hop() -> None:
    req = _request({"x-forwarded-for": "9.9.9.9, 10.0.0.5"}, peer="10.0.0.1")
    # Един доверен прокси → истинският клиент е първият отдясно.
    assert client_ip(req, trusted_proxy_hops=1) == "10.0.0.5"
