"""Пласт за сигурност на публичното API (режим C).

Съдържа защитата на приложния слой: конфигурация, защитни хедъри, CORS, ограничаване
на честотата, лимити за размер, безопасно обработване на грешки и валидация на входа.

Режим C (docs/review-model.md): написан е от водещия разработчик и подлежи на експертен
одит по сигурност. Външните конектори (идентичност, тайни, жив proxy) са зад ясни
интерфейси и се включват отделно.
"""

from __future__ import annotations

from .config import SecurityConfig
from .middleware import install_security
from .secrets import (
    EnvSecretProvider,
    SecretNotFound,
    SecretProvider,
    get_secret_provider,
    redact,
)
from .ssrf import (
    SafeFetchPolicy,
    SsrfError,
    fetch,
    is_blocked_address,
    validate_target,
)
from .validation import validate_identifier

__all__ = [
    "EnvSecretProvider",
    "SafeFetchPolicy",
    "SecretNotFound",
    "SecretProvider",
    "SecurityConfig",
    "SsrfError",
    "fetch",
    "get_secret_provider",
    "install_security",
    "is_blocked_address",
    "redact",
    "validate_identifier",
    "validate_target",
]
