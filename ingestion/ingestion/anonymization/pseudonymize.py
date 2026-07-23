"""Еднопосочна псевдонимизация с тайна сол (чл. 15, ал. 4).

Ядрото е HMAC-SHA256 с таен ключ (**pepper**, държан извън данните) над стойност, съставена от
контекстна сол + нормализиран идентификатор. HMAC е еднопосочен и без тайния pepper псевдонимът
не може да се обърне или преизчисли, дори при известни входни идентификатори.

- **Детерминизъм в контекст:** един и същ (pepper, context) → един и същ псевдоним, за да може
  наборът да се агрегира/свързва вътрешно.
- **Несвързваемост между контексти:** различен ``context`` (напр. различен набор) → различни
  псевдоними за същия субект, което пречи на свързване между набори.
- **Fail-closed:** твърде къс pepper, празен контекст или празен идентификатор вдигат грешка.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import unicodedata
from dataclasses import dataclass, field

# Минимална дължина на тайната. 16 байта ентропия е долната практична граница за таен ключ.
_MIN_PEPPER_BYTES = 16
# Дължина на псевдонима в hex символи. 32 hex = 128 бита — устойчиво на колизии; таван 64 = пълен
# SHA-256 (256 бита); долна граница 16 hex = 64 бита за малки домейни (с документиран риск).
_MIN_TOKEN_HEX = 16
_MAX_TOKEN_HEX = 64
_DEFAULT_TOKEN_HEX = 32
# Разделител, който не може да се появи в нормализиран текст — премахва двусмислие context||id.
_SEP = b"\x1f"

_PEPPER_ENV = "OHDP_SECRET_PEPPER"


class AnonymizationError(RuntimeError):
    """Невалидна конфигурация или вход за псевдонимизация (fail-closed)."""


def _normalize(value: str) -> str:
    """NFC + trim, за да не се разминават псевдоними заради представяне/интервали."""
    return unicodedata.normalize("NFC", value.strip())


@dataclass(frozen=True)
class Pseudonymizer:
    """Еднопосочно преобразуване идентификатор → псевдоним за конкретен контекст."""

    pepper: bytes
    context: str
    token_hex_length: int = _DEFAULT_TOKEN_HEX

    def __post_init__(self) -> None:
        if len(self.pepper) < _MIN_PEPPER_BYTES:
            raise AnonymizationError(
                f"pepper е твърде къс: {len(self.pepper)} < {_MIN_PEPPER_BYTES} байта"
            )
        if not self.context.strip():
            raise AnonymizationError("context (солта) е задължителен и не може да е празен")
        if not _MIN_TOKEN_HEX <= self.token_hex_length <= _MAX_TOKEN_HEX:
            raise AnonymizationError(
                f"token_hex_length извън [{_MIN_TOKEN_HEX}, {_MAX_TOKEN_HEX}]: "
                f"{self.token_hex_length}"
            )

    def token(self, identifier: str) -> str:
        """Връща псевдонима на ``identifier`` в текущия контекст."""
        norm = _normalize(identifier)
        if not norm:
            raise AnonymizationError("празен идентификатор не може да се псевдонимизира")
        msg = self.context.encode("utf-8") + _SEP + norm.encode("utf-8")
        digest = hmac.new(self.pepper, msg, hashlib.sha256).hexdigest()
        return digest[: self.token_hex_length]

    @classmethod
    def from_env(cls, context: str, *, token_hex_length: int = _DEFAULT_TOKEN_HEX) -> Pseudonymizer:
        """Създава псевдонимизатор с pepper от ``OHDP_SECRET_PEPPER`` (fail-closed при липса).

        Тайната се чете от средата, за да не влиза в кода/данните. За продукция pepper-ът идва
        от мениджър на тайни (виж api.security.secrets); тук четенето е нарочно минимално.
        """
        raw = os.environ.get(_PEPPER_ENV, "")
        if not raw:
            raise AnonymizationError(f"липсва тайна {_PEPPER_ENV} (fail-closed)")
        return cls(pepper=raw.encode("utf-8"), context=context, token_hex_length=token_hex_length)


@dataclass(frozen=True)
class PseudonymSpec:
    """Декларация кои колони съдържат преки идентификатори.

    ``columns`` се заменят със псевдоними; ``drop_columns`` се премахват изцяло (идентификатори,
    които изобщо не бива да напускат тръбата).
    """

    columns: list[str] = field(default_factory=list)
    drop_columns: list[str] = field(default_factory=list)


def pseudonymize_rows(
    rows: list[dict[str, object]], spec: PseudonymSpec, pseudonymizer: Pseudonymizer
) -> list[dict[str, object]]:
    """Прилага псевдонимизация по ``spec``. Входът не се мутира; връща нови редове."""
    out: list[dict[str, object]] = []
    for row in rows:
        new_row = dict(row)
        for col in spec.columns:
            value = new_row.get(col)
            if value is not None:
                new_row[col] = pseudonymizer.token(str(value))
        for col in spec.drop_columns:
            new_row.pop(col, None)
        out.append(new_row)
    return out
