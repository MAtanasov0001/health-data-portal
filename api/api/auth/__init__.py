"""Рамка за идентичност и оторизация на публичното API (режим C).

Порталът е публичен и четящ — удостоверяване НЕ се изисква по подразбиране. Рамката е готов
seam за бъдещи защитени операции: pluggable :class:`IdentityProvider`, доставчик само за
разработка (статични токени), plug-point за национална е-идентификация + MFA и fail-closed
route guard.

Режим C (docs/review-model.md): написано от водещия разработчик, подлежи на експертен одит по
сигурност преди активиране на защитени маршрути.
"""

from __future__ import annotations

from .guard import get_auth_config, get_identity_provider, require_auth
from .models import AuthError, Principal
from .providers import (
    AuthConfig,
    DisabledIdentityProvider,
    IdentityProvider,
    StaticTokenIdentityProvider,
    build_provider,
)

__all__ = [
    "AuthConfig",
    "AuthError",
    "DisabledIdentityProvider",
    "IdentityProvider",
    "Principal",
    "StaticTokenIdentityProvider",
    "build_provider",
    "get_auth_config",
    "get_identity_provider",
    "require_auth",
]
