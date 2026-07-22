import json
from pathlib import Path

import pytest

from ingestion.dcat.validate import load_profile, validate_dataset
from ingestion.pipeline import run

PILOT = Path(__file__).resolve().parents[2] / "pilot" / "hospitalizacii-po-oblast-2023"


def test_pilot_end_to_end(tmp_path: Path):
    result = run(PILOT, tmp_path)
    snap = result.snapshot

    # Снапшотът е записан с манифест и контролна сума.
    assert (snap.path / "data.csv").exists()
    manifest = json.loads((snap.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["checksum_sha256"] == snap.checksum_sha256
    assert len(snap.checksum_sha256) == 64
    assert snap.created_at.endswith("+02:00")

    # Пилотът съдържа клетка "<5" → поне едно потискане.
    assert result.suppressed >= 1

    # DCAT-AP записът е валиден спрямо профила.
    record = json.loads(result.dcat_path.read_text(encoding="utf-8"))
    assert validate_dataset(record, load_profile()) == []


def test_snapshot_is_immutable(tmp_path: Path):
    run(PILOT, tmp_path)
    with pytest.raises(FileExistsError):
        run(PILOT, tmp_path)
