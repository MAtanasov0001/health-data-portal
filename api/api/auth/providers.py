"""Доставчици на идентичност (pluggable) + конфигурация и избор на бекенд.

Порталът е публичен и четящ — по подразбиране удостоверяване НЕ се изисква на нито една
крайна точка. Тази рамка е seam за бъдещи защитени операции (напр. администриране/публикуване
или удостоверен харвест). Реалният доставчик (национална е-идентификация + MFA) се включва през
``OHDP_AUTH_BACKEND``, без промяна в guard-а или крайните точки.

Режим C (docs/review-model.md): критичен компонент — подлежи на одит по сигурност.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .models import AuthError, Principal


@runtime_checkable
class IdentityProvider(Protocol):
    """Проверява удостоверение (bearer токен) и връща :class:`Principal` или вдига AuthError."""

    def verify(self, token: str) -> Principal: ...


class DisabledIdentityProvider:
    """Отказва всяко удостоверяване (fail-closed) — бекенд по подразбиране.

    Защитените маршрути връщат 401, докато не се конфигурира реален доставчик; така никога не
    се „отваря" защита случайно.
    """

    def verify(self, token: str) -> Principal:
        raise AuthError("удостоверяването е изключено (няма конфигуриран доставчик)")


@dataclass(frozen=True)
class StaticTokenIdentityProvider:
    """Доставчик само за разработка: статични токени → идентичности.

    НЕ е за продукция. Токените се сравняват в постоянно време (без изтичане по време).
    """

    tokens: dict[str, Principal]

    def verify(self, token: str) -> Principal:
        for candidate, principal in self.tokens.items():
            if hmac.compare_digest(candidate, token):
                return principal
        raise AuthError("невалиден токен")

    @classmethod
    def from_spec(cls, spec: str) -> StaticTokenIdentityProvider:
        """Парсва ``token:subject:scopeA|scopeB[:mfa]`` записи, разделени със запетая."""
        tokens: dict[str, Principal] = {}
        for entry in (e.strip() for e in spec.split(",") if e.strip()):
            parts = entry.split(":")
            if len(parts) < 2:
                raise ValueError(f"невалиден запис за токен: {entry!r}")
            token, subject = parts[0], parts[1]
            scopes = frozenset(s for s in (parts[2].split("|") if len(parts) > 2 else []) if s)
            mfa = len(parts) > 3 and parts[3].strip().lower() in {"1", "true", "yes", "mfa"}
            tokens[token] = Principal(
                subject=subject, scopes=scopes, auth_method="localdev", mfa=mfa
            )
        return cls(tokens)


@dataclass(frozen=True)
class AuthConfig:
    """Кой бекенд за идентичност е активен."""

    backend: str = "disabled"
    dev_tokens: str = ""

    @classmethod
    def from_env(cls) -> AuthConfig:
        return cls(
            backend=os.environ.get("OHDP_AUTH_BACKEND", "disabled").strip().lower(),
            dev_tokens=os.environ.get("OHDP_AUTH_DEV_TOKENS", ""),
        )


def build_provider(config: AuthConfig) -> IdentityProvider:
    """Избира доставчик по конфигурацията (един вход за регистрация на бекенди)."""
    if config.backend in ("", "disabled"):
        return DisabledIdentityProvider()
    if config.backend == "localdev":
        return StaticTokenIdentityProvider.from_spec(config.dev_tokens)
    # Plug-point: национална е-идентификация (OIDC/SAML) + MFA. Реализира се в режим C с ревю,
    # когато пристигне интеграционният слой — умишлено без мълчалив fallback.
    raise NotImplementedError(
        f"бекенд за идентичност {config.backend!r} все още не е свързан — добави IdentityProvider "
        "и го регистрирай в build_provider()"
    )
