"""Оркестрация на приемната тръба + CLI.

вход (директория с source.csv + metadata.yaml + schema.yaml)
  → схемна валидация → контрол на разкриването → неизменяем версиониран снапшот → DCAT-AP запис
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import disclosure
from .audit import AuditTrail, EventType, Outcome, Priority
from .dcat.build import build_dataset
from .models import DatasetMetadata, DatasetSchema, SchemaValidationError, validate_rows
from .snapshot import Snapshot, write_snapshot

_AUDIT_COMPONENT = "ingestion.pipeline"


@dataclass
class IngestResult:
    snapshot: Snapshot
    dcat_path: Path
    suppressed: int


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _default_trail(out_root: Path) -> AuditTrail:
    """Централизиран одитен дневник за приеманията (МЕ64) — един файл за всички набори."""
    return AuditTrail(out_root / "audit" / "ingest-audit.jsonl", component=_AUDIT_COMPONENT)


def run(dataset_dir: Path, out_root: Path, *, audit: AuditTrail | None = None) -> IngestResult:
    """Пуска един набор през цялата тръба и връща резултата.

    Всяка стъпка оставя одитен запис по МЕ64; при отхвърляне по схема се записва събитие с
    приоритет ``error`` и резултат ``failure``, след което грешката се препредава.
    """
    trail = audit or _default_trail(out_root)
    trail.record(
        EventType.INGEST_STARTED,
        f"Стартирано приемане от {dataset_dir}",
        event_data={"dataset_dir": str(dataset_dir)},
    )

    schema = DatasetSchema.from_yaml(dataset_dir / "schema.yaml")
    metadata = DatasetMetadata.from_yaml(dataset_dir / "metadata.yaml")
    raw = _read_csv(dataset_dir / "source.csv")

    try:
        normalized = validate_rows(raw, schema)
    except SchemaValidationError as exc:
        trail.record(
            EventType.SCHEMA_REJECTED,
            f"Входът е отхвърлен: {exc}",
            priority=Priority.ERROR,
            outcome=Outcome.FAILURE,
            event_data={"identifier": metadata.identifier, "reason": str(exc)},
        )
        raise
    trail.record(
        EventType.SCHEMA_VALIDATED,
        f"Схемата е валидирана: {len(normalized)} реда",
        event_data={"identifier": metadata.identifier, "rows": len(normalized)},
    )

    controlled, report = disclosure.apply(normalized, schema.disclosure)
    trail.record(
        EventType.DISCLOSURE_APPLIED,
        f"Приложен контрол на разкриването: {report.total_suppressed} потиснати клетки",
        event_data={
            "identifier": metadata.identifier,
            "min_cell_size": report.min_cell_size,
            "primary_suppressed": report.primary_suppressed,
            "secondary_suppressed": report.secondary_suppressed,
        },
    )

    columns = [c.name for c in schema.columns]
    snapshot = write_snapshot(
        out_root=out_root,
        metadata=metadata,
        columns=columns,
        rows=controlled,
        disclosure=report,
    )
    trail.record(
        EventType.SNAPSHOT_WRITTEN,
        f"Записан снапшот {snapshot.identifier}@{snapshot.version}",
        event_data={
            "identifier": snapshot.identifier,
            "version": snapshot.version,
            "checksum_sha256": snapshot.checksum_sha256,
            "row_count": snapshot.row_count,
        },
    )

    dcat_record = build_dataset(metadata, snapshot, report)
    dcat_path = snapshot.path / "dcat.jsonld"
    dcat_path.write_text(
        json.dumps(dcat_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    trail.record(
        EventType.DCAT_BUILT,
        f"Изграден DCAT-AP запис за {snapshot.identifier}@{snapshot.version}",
        event_data={"dcat_path": str(dcat_path)},
    )

    trail.record(
        EventType.INGEST_COMPLETED,
        f"Приключено приемане на {snapshot.identifier}@{snapshot.version}",
        event_data={"identifier": snapshot.identifier, "version": snapshot.version},
    )
    return IngestResult(snapshot=snapshot, dcat_path=dcat_path, suppressed=report.total_suppressed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ohdp-ingest", description="Приемна тръба на портала")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Пусни набор през тръбата")
    run_p.add_argument(
        "dataset_dir",
        type=Path,
        help="Директория с source.csv/metadata.yaml/schema.yaml",
    )
    run_p.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "snapshots",
        help="Коренна директория за снапшоти (по подразбиране ingestion/snapshots)",
    )

    args = parser.parse_args(argv)
    if args.cmd == "run":
        result = run(args.dataset_dir, args.out)
        s = result.snapshot
        print(f"✓ Снапшот: {s.identifier}@{s.version}")
        print(f"  създаден: {s.created_at}")
        print(f"  редове:   {s.row_count}")
        print(f"  SHA-256:  {s.checksum_sha256}")
        print(f"  потиснати клетки: {result.suppressed}")
        print(f"  DCAT-AP:  {result.dcat_path}")
        print(f"  одит (МЕ64): {args.out / 'audit' / 'ingest-audit.jsonl'}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
