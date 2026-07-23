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
from .validation import validate_identifier

__all__ = ["SecurityConfig", "install_security", "validate_identifier"]
