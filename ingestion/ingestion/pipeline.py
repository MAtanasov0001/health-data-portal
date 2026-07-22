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
from .dcat.build import build_dataset
from .models import DatasetMetadata, DatasetSchema, validate_rows
from .snapshot import Snapshot, write_snapshot


@dataclass
class IngestResult:
    snapshot: Snapshot
    dcat_path: Path
    suppressed: int


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def run(dataset_dir: Path, out_root: Path) -> IngestResult:
    """Пуска един набор през цялата тръба и връща резултата."""
    schema = DatasetSchema.from_yaml(dataset_dir / "schema.yaml")
    metadata = DatasetMetadata.from_yaml(dataset_dir / "metadata.yaml")
    raw = _read_csv(dataset_dir / "source.csv")

    normalized = validate_rows(raw, schema)
    controlled, report = disclosure.apply(normalized, schema.disclosure)

    columns = [c.name for c in schema.columns]
    snapshot = write_snapshot(
        out_root=out_root,
        metadata=metadata,
        columns=columns,
        rows=controlled,
        disclosure=report,
    )

    dcat_record = build_dataset(metadata, snapshot, report)
    dcat_path = snapshot.path / "dcat.jsonld"
    dcat_path.write_text(
        json.dumps(dcat_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return IngestResult(snapshot=snapshot, dcat_path=dcat_path, suppressed=report.total_suppressed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ohdp-ingest", description="Приемна тръба на портала")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Пусни набор през тръбата")
    run_p.add_argument("dataset_dir", type=Path, help="Директория с source.csv/metadata.yaml/schema.yaml")
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
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
