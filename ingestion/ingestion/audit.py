"""Одитен модул по МЕ64 — проследимост на административните действия в приемната тръба.

Всеки одитен запис носи деветте задължителни атрибута по МЕ64 (концепция v2.0, 10.5):

1. ``record_id``   — уникален номер на записа
2. ``occurred_at`` — точно време на възникване (ISO-8601 / UTC+2, чл. 46)
3. ``event_type``  — вид на събитието по номенклатура (:class:`EventType`)
4. ``system``      — данни за системата, регистрирала събитието (име и версия)
5. ``component``   — идентификатор на компонента-източник
6. ``priority``    — приоритет/важност на събитието (:class:`Priority`)
7. ``description`` — описание на събитието (четимо от човек)
8. ``event_data``  — данни, свързани със събитието (структуриран payload)
9. ``outcome``     — резултат от обработката на събитието (:class:`Outcome`)

Записът е само за добавяне (append-only) и се сериализира като JSON Lines — формат, удобен за
централизиране и подаване към SIEM (МЕ64). Няма изтриване или презапис на редове.

Режим B (ревюиращ ≠ автор): деветият атрибут (``outcome`` — резултат от обработката) реализира
изискването „резултат от събитието"; мапингът на деветте атрибута подлежи на потвърждение при ревю.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import __version__
from .timeutil import now_iso

SYSTEM_NAME = "ohdp-ingestion"
#: Данни за системата (атрибут 4) — име и версия на приемната тръба.
SYSTEM = f"{SYSTEM_NAME}@{__version__}"


class EventType(StrEnum):
    """Вид на събитието по номенклатура (атрибут 3 по МЕ64)."""

    INGEST_STARTED = "ingest.started"
    SCHEMA_VALIDATED = "ingest.schema.validated"
    SCHEMA_REJECTED = "ingest.schema.rejected"
    DISCLOSURE_APPLIED = "ingest.disclosure.applied"
    SNAPSHOT_WRITTEN = "ingest.snapshot.written"
    DCAT_BUILT = "ingest.dcat.built"
    INGEST_COMPLETED = "ingest.completed"
    INGEST_FAILED = "ingest.failed"


class Priority(StrEnum):
    """Приоритет/важност на събитието (атрибут 6 по МЕ64)."""

    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Outcome(StrEnum):
    """Резултат от обработката на събитието (атрибут 9 по МЕ64)."""

    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True)
class AuditEvent:
    """Неизменяем одитен запис с деветте задължителни атрибута по МЕ64."""

    record_id: str
    occurred_at: str
    event_type: EventType
    system: str
    component: str
    priority: Priority
    description: str
    event_data: dict[str, Any] = field(default_factory=dict)
    outcome: Outcome = Outcome.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """Записът като подреден речник (редът следва номерацията на атрибутите по МЕ64)."""
        return {
            "record_id": self.record_id,
            "occurred_at": self.occurred_at,
            "event_type": self.event_type.value,
            "system": self.system,
            "component": self.component,
            "priority": self.priority.value,
            "description": self.description,
            "event_data": self.event_data,
            "outcome": self.outcome.value,
        }

    def to_json(self) -> str:
        """Един ред JSON (без нови редове вътре) — за JSON Lines дневник."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=False)


class AuditTrail:
    """Само-за-добавяне дневник на одитни събития (JSON Lines).

    Часовникът и генераторът на идентификатори се инжектират, за да е тестируемо и
    детерминистично. Файлът се отваря в режим на добавяне при всеки запис — редове не се
    променят и не се трият (МЕ64: забрана за подмяна на журнала).
    """

    def __init__(
        self,
        path: Path,
        *,
        component: str,
        system: str = SYSTEM,
        clock: Callable[[], str] = now_iso,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self.path = path
        self.component = component
        self.system = system
        self._clock = clock
        self._id_factory = id_factory
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        event_type: EventType,
        description: str,
        *,
        priority: Priority = Priority.INFO,
        outcome: Outcome = Outcome.SUCCESS,
        event_data: dict[str, Any] | None = None,
        component: str | None = None,
    ) -> AuditEvent:
        """Създава събитие, добавя го към дневника и го връща."""
        event = AuditEvent(
            record_id=self._id_factory(),
            occurred_at=self._clock(),
            event_type=event_type,
            system=self.system,
            component=component or self.component,
            priority=priority,
            description=description,
            event_data=event_data or {},
            outcome=outcome,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(event.to_json() + "\n")
        return event

    def events(self) -> list[AuditEvent]:
        """Прочита дневника обратно (за проверка/тестове)."""
        if not self.path.exists():
            return []
        out: list[AuditEvent] = []
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                out.append(
                    AuditEvent(
                        record_id=d["record_id"],
                        occurred_at=d["occurred_at"],
                        event_type=EventType(d["event_type"]),
                        system=d["system"],
                        component=d["component"],
                        priority=Priority(d["priority"]),
                        description=d["description"],
                        event_data=d["event_data"],
                        outcome=Outcome(d["outcome"]),
                    )
                )
        return out
