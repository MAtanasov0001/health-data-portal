"""Ограничаване на честотата на заявките (пласт на достъпност/злоупотреба).

Реализацията е с плъзгащ прозорец в паметта и е зад **абстрактен интерфейс**
(``RateLimiterBackend``), за да може лесно да се замени с разпределен backend (напр.
Redis) при мащабиране, без да се пипа middleware-ът. По подразбиране лимитерът е
**fail-open**: при вътрешна грешка достъпът до отворените данни не се блокира.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Protocol


class RateLimiterBackend(Protocol):
    """Договор за backend за ограничаване на честотата."""

    def hit(self, key: str) -> tuple[bool, int]:
        """Регистрира заявка за ``key``.

        Връща ``(allowed, retry_after_seconds)``. При ``allowed == False``
        ``retry_after`` е броят секунди до освобождаване на квота.
        """
        ...


class InMemoryRateLimiter:
    """Плъзгащ прозорец в паметта (за единичен процес/локална среда).

    Не е подходящ за много реплики (всяка има собствен брояч); за продукция се
    инжектира разпределен backend със същия интерфейс.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = max(1, limit)
        self._window = max(1, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self._window
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self._limit:
            retry_after = int(bucket[0] + self._window - now) + 1
            return False, max(1, retry_after)
        bucket.append(now)
        return True, 0
