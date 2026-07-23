"""Основни типове за идентичност: удостоверен субект и грешка при удостоверяване.

Режим C (docs/review-model.md): критичен компонент — подлежи на одит по сигурност.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


class AuthError(Exception):
    """Удостоверяването се провали (невалиден/липсващ токен). Fail-closed сигнал към guard-а."""


@dataclass(frozen=True)
class Principal:
    """Удостоверена идентичност след успешна проверка на удостоверение.

    ``scopes`` са гранулираните права; ``mfa`` показва дали удостоверяването е било с втори
    фактор (изисква се от route guard за чувствителни операции); ``auth_method`` записва как е
    удостоверен субектът (напр. ``localdev``, ``eid``), за одит.
    """

    subject: str
    display_name: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    auth_method: str = "unknown"
    mfa: bool = False
    attributes: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def has_scopes(self, required: frozenset[str]) -> bool:
        return required <= self.scopes
