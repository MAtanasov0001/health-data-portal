"""Неизменяем версиониран снапшот с контролна сума (SHA-256) и времеви печат (ISO 8601 / UTC+2)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .disclosure import DisclosureReport
from .models import DatasetMetadata
from .timeutil import now_iso


@dataclass
class Snapshot:
    identifier: str
    version: str
    created_at: str
    checksum_sha256: str
    row_count: int
    path: Path


def _rows_to_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: ("" if row.get(c) is None else row[c]) for c in columns})
    return buf.getvalue()


def write_snapshot(
    *,
    out_root: Path,
    metadata: DatasetMetadata,
    columns: list[str],
    rows: list[dict[str, Any]],
    disclosure: DisclosureReport,
) -> Snapshot:
    """Записва неизменяем снапшот. Отказва да презапише съществуваща версия."""
    target = out_root / metadata.identifier / metadata.version
    if target.exists():
        raise FileExistsError(
            f"Снапшот {metadata.identifier}@{metadata.version} вече съществува — "
            f"версиите са неизменяеми (чл. 14). Вдигни версията в metadata.yaml."
        )

    csv_text = _rows_to_csv(rows, columns)
    checksum = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    created_at = now_iso()

    target.mkdir(parents=True, exist_ok=False)
    (target / "data.csv").write_text(csv_text, encoding="utf-8")

    manifest = {
        "identifier": metadata.identifier,
        "version": metadata.version,
        "created_at": created_at,
        "checksum_sha256": checksum,
        "row_count": len(rows),
        "columns": columns,
        "disclosure_control": {
            "method": "small-cell-suppression",
            "min_cell_size": disclosure.min_cell_size,
            "primary_suppressed": disclosure.primary_suppressed,
            "secondary_suppressed": disclosure.secondary_suppressed,
            "total_cells": disclosure.total_cells,
        },
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return Snapshot(
        identifier=metadata.identifier,
        version=metadata.version,
        created_at=created_at,
        checksum_sha256=checksum,
        row_count=len(rows),
        path=target,
    )
