"""Тестове за одитния модул по МЕ64 и интеграцията му в приемната тръба."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from ingestion.audit import (
    SYSTEM,
    AuditTrail,
    EventType,
    Outcome,
    Priority,
)
from ingestion.models import SchemaValidationError
from ingestion.pipeline import run

PILOT = Path(__file__).resolve().parents[2] / "pilot" / "hospitalizacii-po-oblast-2023"

# Деветте задължителни атрибута по МЕ64 (концепция v2.0, 10.5).
_ME64_ATTRS = {
    "record_id",
    "occurred_at",
    "event_type",
    "system",
    "component",
    "priority",
    "description",
    "event_data",
    "outcome",
}


def _fixed_trail(path: Path) -> AuditTrail:
    counter = itertools.count(1)
    return AuditTrail(
        path,
        component="test.component",
        clock=lambda: "2026-07-23T10:00:00+02:00",
        id_factory=lambda: f"rec-{next(counter):04d}",
    )


def test_record_has_all_nine_me64_attributes(tmp_path: Path):
    trail = _fixed_trail(tmp_path / "audit.jsonl")
    event = trail.record(EventType.INGEST_STARTED, "старт")
    assert set(event.to_dict()) == _ME64_ATTRS


def test_record_serialized_line_is_single_json_object(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    trail = _fixed_trail(path)
    trail.record(EventType.INGEST_STARTED, "старт")
    trail.record(EventType.INGEST_COMPLETED, "край")
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["record_id"] == "rec-0001"
    assert first["occurred_at"] == "2026-07-23T10:00:00+02:00"
    assert first["system"] == SYSTEM
    assert first["event_type"] == "ingest.started"


def test_defaults_are_info_and_success(tmp_path: Path):
    trail = _fixed_trail(tmp_path / "audit.jsonl")
    event = trail.record(EventType.SNAPSHOT_WRITTEN, "снапшот")
    assert event.priority is Priority.INFO
    assert event.outcome is Outcome.SUCCESS


def test_trail_is_append_only(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    trail = _fixed_trail(path)
    trail.record(EventType.INGEST_STARTED, "едно")
    trail.record(EventType.INGEST_STARTED, "две")
    trail.record(EventType.INGEST_STARTED, "три")
    assert len(trail.events()) == 3  # нищо не се презаписва


def test_events_roundtrip_preserves_enums(tmp_path: Path):
    trail = _fixed_trail(tmp_path / "audit.jsonl")
    trail.record(
        EventType.SCHEMA_REJECTED,
        "отхвърлен",
        priority=Priority.ERROR,
        outcome=Outcome.FAILURE,
        event_data={"reason": "лош ред"},
    )
    (event,) = trail.events()
    assert event.event_type is EventType.SCHEMA_REJECTED
    assert event.priority is Priority.ERROR
    assert event.outcome is Outcome.FAILURE
    assert event.event_data == {"reason": "лош ред"}


def test_pipeline_emits_full_audit_trail(tmp_path: Path):
    trail = _fixed_trail(tmp_path / "audit" / "ingest.jsonl")
    run(PILOT, tmp_path / "snapshots", audit=trail)
    kinds = [e.event_type for e in trail.events()]
    assert kinds == [
        EventType.INGEST_STARTED,
        EventType.SCHEMA_VALIDATED,
        EventType.DISCLOSURE_APPLIED,
        EventType.SNAPSHOT_WRITTEN,
        EventType.DCAT_BUILT,
        EventType.INGEST_COMPLETED,
    ]
    # Всяко събитие носи деветте атрибута и е успешно.
    for e in trail.events():
        assert set(e.to_dict()) == _ME64_ATTRS
        assert e.outcome is Outcome.SUCCESS


def test_pipeline_default_trail_writes_central_log(tmp_path: Path):
    out = tmp_path / "snapshots"
    run(PILOT, out)
    log = out / "audit" / "ingest-audit.jsonl"
    assert log.exists()
    assert "ingest.completed" in log.read_text(encoding="utf-8")


def test_pipeline_records_rejection(tmp_path: Path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "schema.yaml").write_text(
        (PILOT / "schema.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (bad / "metadata.yaml").write_text(
        (PILOT / "metadata.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (bad / "source.csv").write_text("bogus,columns\n1,2\n", encoding="utf-8")

    trail = _fixed_trail(tmp_path / "audit" / "ingest.jsonl")
    with pytest.raises(SchemaValidationError):
        run(bad, tmp_path / "snapshots", audit=trail)

    events = trail.events()
    assert events[-1].event_type is EventType.SCHEMA_REJECTED
    assert events[-1].priority is Priority.ERROR
    assert events[-1].outcome is Outcome.FAILURE
