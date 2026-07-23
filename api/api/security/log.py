"""Структуриран журнал за събития по сигурността (SIEM-съвместим, без лични данни).

Не пишем тела на заявки или лични данни — само метаданни за събитието (тип, клиентски
IP, път, корелационен идентификатор). Изходът е JSON на ред, за да се поглъща лесно от
централизирано журналиране (концепция v2.0 — централизиран одит).
"""

from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger("ohdp.security")


def security_event(event: str, *, level: int = logging.WARNING, **fields: Any) -> None:
    """Издава едно събитие по сигурността като структуриран JSON ред."""
    payload: dict[str, Any] = {"event": event, **fields}
    _logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))
