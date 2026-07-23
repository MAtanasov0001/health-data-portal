"""Инсталиране на защитните пластове върху FastAPI приложението.

Един вход — :func:`install_security` — регистрира: CORS политика, ограничаване на
честотата, лимит за размер на тялото, защитни HTTP хедъри и безопасно обработване на
грешки (без изтичане на вътрешна информация). Всичко е конфигурируемо през
:class:`SecurityConfig` и е secure-by-default.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.responses import Response

from .config import SecurityConfig
from .log import security_event
from .net import client_ip
from .ratelimit import InMemoryRateLimiter, RateLimiterBackend

_logger = logging.getLogger("ohdp.security")

Handler = Callable[[Request], Awaitable[Response]]

# Пътища без ограничаване на честотата (проверки на живост от оркестратора).
_RATELIMIT_EXEMPT = frozenset({"/v1/health"})


def _security_headers(config: SecurityConfig) -> dict[str, str]:
    """Статичните защитни хедъри за всеки отговор (API връща данни, не HTML)."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        ),
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Opener-Policy": "same-origin",
        # Отворените данни трябва да могат да се четат крос-ориджин от харвестъри/frontend.
        "Cross-Origin-Resource-Policy": "cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=(), interest-cohort=()",
    }
    if config.hsts_enabled:
        headers["Strict-Transport-Security"] = (
            f"max-age={config.hsts_max_age}; includeSubDomains; preload"
        )
    return headers


def install_security(
    app: FastAPI,
    config: SecurityConfig | None = None,
    *,
    rate_limiter: RateLimiterBackend | None = None,
) -> None:
    """Регистрира всички защитни пластове върху ``app``."""
    cfg = config or SecurityConfig.from_env()
    limiter = rate_limiter or InMemoryRateLimiter(
        cfg.rate_limit_requests, cfg.rate_limit_window_seconds
    )
    static_headers = _security_headers(cfg)

    if cfg.cors_allow_all or cfg.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"] if cfg.cors_allow_all else cfg.cors_origins,
            allow_credentials=False,  # публични данни — без бисквитки/удостоверяване
            allow_methods=["GET", "HEAD", "OPTIONS"],
            allow_headers=["Accept", "Content-Type"],
            max_age=600,
        )

    @app.middleware("http")
    async def _security_layer(request: Request, call_next: Handler) -> Response:
        # 1) Лимит за размер на тялото (изчерпване на ресурси). API-то е четящо.
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > cfg.max_body_bytes:
                    security_event(
                        "body_too_large",
                        path=request.url.path,
                        ip=client_ip(request, cfg.trusted_proxy_hops),
                        declared=int(declared),
                    )
                    resp = PlainTextResponse("Тялото е твърде голямо", 413)
                    return _headers(resp, static_headers)
            except ValueError:
                resp = PlainTextResponse("Невалиден Content-Length", 400)
                return _headers(resp, static_headers)

        # 2) Ограничаване на честотата (fail-open при вътрешна грешка).
        if cfg.rate_limit_enabled and request.url.path not in _RATELIMIT_EXEMPT:
            ip = client_ip(request, cfg.trusted_proxy_hops)
            try:
                allowed, retry_after = limiter.hit(ip)
            except Exception:  # noqa: BLE001 — достъпността на отворените данни е с приоритет
                _logger.exception("rate limiter error — fail-open")
                allowed, retry_after = True, 0
            if not allowed:
                security_event(
                    "rate_limited", path=request.url.path, ip=ip, retry_after=retry_after
                )
                resp = PlainTextResponse("Твърде много заявки", 429)
                resp.headers["Retry-After"] = str(retry_after)
                return _headers(resp, static_headers)

        # 3) Обработка на заявката с безопасно улавяне на неочаквани грешки.
        try:
            response = await call_next(request)
        except Exception:
            correlation_id = uuid.uuid4().hex
            _logger.exception("unhandled error correlation_id=%s", correlation_id)
            security_event(
                "internal_error",
                level=logging.ERROR,
                path=request.url.path,
                correlation_id=correlation_id,
            )
            error_resp: Response = JSONResponse(
                {"error": "internal_error", "correlation_id": correlation_id},
                status_code=500,
            )
            return _headers(error_resp, static_headers)

        return _headers(response, static_headers)


def _headers(response: Response, static_headers: dict[str, str]) -> Response:
    for name, value in static_headers.items():
        response.headers.setdefault(name, value)
    # Намаляваме отпечатъка на сървъра (fingerprinting).
    if "server" in response.headers:
        del response.headers["server"]
    return response
