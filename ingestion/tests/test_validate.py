"""Тестове за DCAT-AP / StatDCAT-AP валидатора и StatDCAT-AP обогатяването при изграждане."""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.dcat.build import build_dataset
from ingestion.dcat.validate import load_profile, validate_dataset
from ingestion.disclosure import DisclosureReport
from ingestion.models import DatasetMetadata, DisclosureSpec
from ingestion.snapshot import Snapshot

_EXAMPLES = Path(__file__).resolve().parents[2] / "spec" / "dcat-ap" / "examples"


def _metadata() -> DatasetMetadata:
    return DatasetMetadata(
        identifier="demo",
        title={"bg": "Демо", "en": "Demo"},
        description={"bg": "описание", "en": "description"},
        publisher="МИДТ",
        contact_email="data@health.egov.bg",
        theme=["HEAL"],
    )


def _snapshot() -> Snapshot:
    return Snapshot(
        identifier="demo",
        version="1.0.0",
        created_at="2026-07-23T10:00:00+02:00",
        checksum_sha256="a" * 64,
        row_count=12,
        path=Path("/tmp/demo"),
    )


def _spec() -> DisclosureSpec:
    return DisclosureSpec(
        measure_column="broy", dimension_columns=["oblast", "grupa"], min_cell_size=5
    )


def test_canonical_example_is_valid():
    record = json.loads((_EXAMPLES / "dataset.jsonld").read_text(encoding="utf-8"))
    assert validate_dataset(record, load_profile()) == []


def test_statistical_missing_dimension_is_flagged():
    profile = load_profile()
    record = json.loads((_EXAMPLES / "dataset.jsonld").read_text(encoding="utf-8"))
    del record["stat:dimension"]  # остава stat:numSeries → все още статистически
    errors = validate_dataset(record, profile)
    assert any("stat:dimension" in e for e in errors)


def test_non_statistical_record_needs_no_stat_props():
    profile = load_profile()
    record = json.loads((_EXAMPLES / "dataset.jsonld").read_text(encoding="utf-8"))
    for key in ("stat:dimension", "stat:attribute", "stat:numSeries"):
        record.pop(key, None)
    assert validate_dataset(record, profile) == []


def test_build_dataset_emits_stat_props_when_spec_given():
    report = DisclosureReport(min_cell_size=5)
    record = build_dataset(_metadata(), _snapshot(), report, stat_spec=_spec())
    assert record["stat:numSeries"]["@value"] == "12"
    labels = [d["skos:prefLabel"]["@value"] for d in record["stat:dimension"]]
    assert labels == ["oblast", "grupa"]
    assert record["stat:attribute"][0]["skos:prefLabel"]["@value"] == "broy"


def test_build_dataset_omits_stat_props_without_spec():
    report = DisclosureReport(min_cell_size=5)
    record = build_dataset(_metadata(), _snapshot(), report)
    assert "stat:dimension" not in record
    assert "stat:numSeries" not in record


def test_generated_stat_record_validates():
    report = DisclosureReport(min_cell_size=5)
    record = build_dataset(_metadata(), _snapshot(), report, stat_spec=_spec())
    assert validate_dataset(record, load_profile()) == []
