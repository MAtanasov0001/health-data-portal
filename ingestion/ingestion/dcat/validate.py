"""Лека валидация на DCAT-AP запис спрямо профила (spec/dcat-ap/profile.json).

Проверява наличието на задължителните (M) свойства за dcat:Dataset и неговите dcat:Distribution.
Пълната SHACL валидация е отделна CI стъпка; тази проверка е бърза и се ползва при приемане.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_PROFILE = Path(__file__).resolve().parents[3] / "spec" / "dcat-ap" / "profile.json"


def _mandatory(profile: dict[str, Any], cls: str) -> list[str]:
    props = profile["classes"][cls]["properties"]
    return [name for name, spec in props.items() if spec.get("obligation") == "M"]


def _is_statistical(record: dict[str, Any]) -> bool:
    """Наборът е статистически, ако носи поне едно StatDCAT-AP свойство (префикс ``stat:``)."""
    return any(key.startswith("stat:") for key in record)


def validate_dataset(record: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Връща списък с грешки (празен = валиден).

    Ако наборът е статистически (носи ``stat:`` свойство), се проверяват и задължителните
    StatDCAT-AP свойства (клас ``StatisticalDataset`` в профила).
    """
    errors: list[str] = []
    for prop in _mandatory(profile, "Dataset"):
        if prop not in record:
            errors.append(f"Липсва задължително свойство на Dataset: {prop}")

    if _is_statistical(record):
        for prop in _mandatory(profile, "StatisticalDataset"):
            if prop not in record:
                errors.append(f"Липсва задължително StatDCAT-AP свойство: {prop}")

    dists = record.get("dcat:distribution", [])
    if not dists:
        errors.append("Dataset няма dcat:distribution (задължително)")
    for i, dist in enumerate(dists):
        for prop in _mandatory(profile, "Distribution"):
            if prop not in dist:
                errors.append(f"Distribution[{i}]: липсва задължително свойство {prop}")
    return errors


def load_profile() -> dict[str, Any]:
    return json.loads(_PROFILE.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(
            "Употреба: python -m ingestion.dcat.validate <dataset.jsonld> [още...]",
            file=sys.stderr,
        )
        return 2
    profile = load_profile()
    failed = False
    for path_str in argv:
        record = json.loads(Path(path_str).read_text(encoding="utf-8"))
        errors = validate_dataset(record, profile)
        if errors:
            failed = True
            for e in errors:
                print(f"::error file={path_str}::{e}", file=sys.stderr)
        else:
            kind = "StatDCAT-AP" if _is_statistical(record) else "DCAT-AP"
            print(f"{kind}: {path_str} — валиден спрямо профила.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
