"""Валидация на потребителски идентификатори преди достъп до файловата система.

Идентификаторът на набор идва от URL пътя и се използва за изграждане на път до
снапшота. Затова го валидираме стриктно (allowlist), за да няма обхождане на пътища
(``..``, наклонени черти, NUL и др.) — защита в дълбочина над проверките на рамката.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

# Малки латински букви, цифри и тирета; без водещо/затварящо тире; до 100 знака.
_SAFE_IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_MAX_LEN = 100


def validate_identifier(identifier: str) -> str:
    """Връща ``identifier``, ако е безопасен; иначе вдига ``HTTPException(400)``."""
    if len(identifier) > _MAX_LEN or not _SAFE_IDENTIFIER.match(identifier):
        raise HTTPException(status_code=400, detail="Невалиден идентификатор на набор")
    return identifier
