"""Времеви печати по ISO 8601, часова зона UTC+2 (Europe/Sofia), от сървъра (чл. 46)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Фиксиран отместване +02:00 съгласно чл. 46 (UTC+2). Не използваме локалната зона на машината,
# за да е печатът детерминистичен и независим от конфигурацията на средата.
UTC_PLUS_2 = timezone(timedelta(hours=2))


def now_iso() -> str:
    """Текущ момент като ISO 8601 низ с отместване +02:00, секундна точност."""
    return datetime.now(UTC_PLUS_2).replace(microsecond=0).isoformat()
