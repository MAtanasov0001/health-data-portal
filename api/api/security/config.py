"""Конфигурация на сигурността на публичното API — от околната среда (12-factor).

Секюрити настройките се четат от env, за да няма тайни/среда в кода и да са различни по
среди (dev/staging/prod). Всички имат сигурни стойности по подразбиране (secure-by-default);
средата само разхлабва там, където е нужно (напр. CORS за конкретен frontend произход).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SecurityConfig:
    """Профил на сигурността, зареден веднъж при стартиране."""

    # CORS — публичните данни са GET-only; по подразбиране позволяваме само познати
    # произходи (frontend-а). ``*`` е допустимо съзнателно за напълно отворени данни.
    cors_origins: list[str] = field(default_factory=list)
    cors_allow_all: bool = False

    # Ограничаване на честотата (на клиентски ключ, обикновено IP).
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    # Колко доверени обратни проксита стоят пред приложението. 0 = не се доверяваме на
    # X-Forwarded-For (иначе клиент може да подправи IP и да заобиколи лимита).
    trusted_proxy_hops: int = 0

    # Максимален размер на тялото на заявка (защита от изчерпване на ресурси). API-то е
    # четящо (GET), затова лимитът е малък.
    max_body_bytes: int = 64 * 1024

    # HSTS — има смисъл само зад TLS; държим го включен по подразбиране (зад терминиращ TLS).
    hsts_enabled: bool = True
    hsts_max_age: int = 63072000  # 2 години

    @classmethod
    def from_env(cls) -> SecurityConfig:
        origins = _split(os.environ.get("OHDP_CORS_ORIGINS", ""))
        allow_all = "*" in origins
        return cls(
            cors_origins=[o for o in origins if o != "*"],
            cors_allow_all=allow_all,
            rate_limit_enabled=_bool("OHDP_RATE_LIMIT_ENABLED", True),
            rate_limit_requests=_int("OHDP_RATE_LIMIT_REQUESTS", 120),
            rate_limit_window_seconds=_int("OHDP_RATE_LIMIT_WINDOW", 60),
            trusted_proxy_hops=_int("OHDP_TRUSTED_PROXY_HOPS", 0),
            max_body_bytes=_int("OHDP_MAX_BODY_BYTES", 64 * 1024),
            hsts_enabled=_bool("OHDP_HSTS_ENABLED", True),
            hsts_max_age=_int("OHDP_HSTS_MAX_AGE", 63072000),
        )
