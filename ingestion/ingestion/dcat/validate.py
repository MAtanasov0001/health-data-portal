"""Лека валидация на DCAT-AP запис спрямо профила (spec/dcat-ap/profile.json).

Проверява наличието на задължителните (M) свойства за dcat:Dataset и неговите dcat:Distribution.
Пълната SHACL валидация е отделна CI стъпка; тази проверка е бърза и се ползва при приемане.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_PROFILE = (
    Path(__file__).resolve().parents[3] / "spec" / "dcat-ap" / "profile.json"
)


def _mandatory(profile: dict[str, Any], cls: str) -> list[str]:
    props = profile["classes"][cls]["properties"]
    return [name for name, spec in props.items() if spec.get("obligation") == "M"]


def validate_dataset(record: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Връща списък с грешки (празен = валиден)."""
    errors: list[str] = []
    for prop in _mandatory(profile, "Dataset"):
        if prop not in record:
            errors.append(f"Липсва задължително свойство на Dataset: {prop}")

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
        print("Употреба: python -m ingestion.dcat.validate <dataset.jsonld>", file=sys.stderr)
        return 2
    record = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    errors = validate_dataset(record, load_profile())
    if errors:
        for e in errors:
            print(f"::error::{e}", file=sys.stderr)
        return 1
    print("DCAT-AP: валиден спрямо профила (задължителни свойства налични).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
