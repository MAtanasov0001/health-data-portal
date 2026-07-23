"""Абстракция за доставчик на тайни (secure seam).

Тайните НИКОГА не се пазят в кода или репото. По подразбиране се четат от околната среда
(12-factor). Интерфейсът е готов за бъдещ мениджър на тайни (HashiCorp Vault, AWS Secrets
Manager, git.egov.bg vault) — новият бекенд се включва през ``OHDP_SECRET_BACKEND``, без да
се пипа извикващият код.

Принципи:
- **Fail-closed:** липсваща задължителна тайна вдига :class:`SecretNotFound`, не връща празно.
- **Без изтичане:** стойностите на тайните не се логват; ползвай :func:`redact` за диагностика.
- **Pluggable:** :class:`SecretProvider` е протокол; реализациите се регистрират в
  :func:`get_secret_provider`.

Режим C (docs/review-model.md): критичен компонент — подлежи на одит по сигурност.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")


class SecretNotFound(RuntimeError):
    """Задължителна тайна липсва в конфигурирания бекенд (fail-closed)."""


@runtime_checkable
class SecretProvider(Protocol):
    """Източник на тайни. Реализациите не логват стойности и се провалят затворено."""

    def get(self, name: str, *, required: bool = True, default: str | None = None) -> str | None:
        """Връща тайната ``name`` или вдига :class:`SecretNotFound`, ако е задължителна и липсва."""
        ...


@dataclass(frozen=True)
class EnvSecretProvider:
    """Чете тайни от околната среда — подразбиращ се бекенд за dev/локална среда.

    Името се нормализира до ``<prefix><UPPER_SNAKE>`` (напр. ``pepper`` → ``OHDP_SECRET_PEPPER``,
    ``auth-signing-key`` → ``OHDP_SECRET_AUTH_SIGNING_KEY``). Празен стринг се третира като липса.
    """

    prefix: str = "OHDP_SECRET_"

    def env_name(self, name: str) -> str:
        return self.prefix + _NON_ALNUM.sub("_", name.upper()).strip("_")

    def get(self, name: str, *, required: bool = True, default: str | None = None) -> str | None:
        raw = os.environ.get(self.env_name(name))
        if raw is None or raw == "":
            if required and default is None:
                raise SecretNotFound(
                    f"липсва задължителна тайна {name!r} (среда {self.env_name(name)})"
                )
            return default
        return raw


def get_secret_provider(backend: str | None = None) -> SecretProvider:
    """Избира доставчик по ``OHDP_SECRET_BACKEND`` (по подразбиране ``env``).

    Бъдещите мениджъри на тайни се регистрират тук (един вход), за да остане извикващият
    код независим от конкретния бекенд.
    """
    resolved = (backend or os.environ.get("OHDP_SECRET_BACKEND", "env")).strip().lower()
    if resolved == "env":
        return EnvSecretProvider()
    # Plug-point: Vault / AWS Secrets Manager / git.egov.bg vault. Реализира се в режим C с
    # ревю, когато пристигне интеграционният слой — умишлено не подаваме мълчалив fallback.
    raise NotImplementedError(
        f"бекенд за тайни {resolved!r} все още не е свързан — добави SecretProvider и го "
        "регистрирай в get_secret_provider()"
    )


def redact(value: str | None, *, keep: int = 0) -> str:
    """Безопасно представяне на тайна за логове/диагностика — никога не разкрива стойността."""
    if not value:
        return "<empty>"
    if keep <= 0 or len(value) <= keep:
        return "***"
    return value[:keep] + "***"
