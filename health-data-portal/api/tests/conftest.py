import json
from pathlib import Path

import pytest


def _write_snapshot(root: Path, identifier: str, version: str, created_at: str) -> None:
    d = root / identifier / version
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(
        json.dumps(
            {
                "identifier": identifier,
                "version": version,
                "created_at": created_at,
                "checksum_sha256": "a" * 64,
                "row_count": 2,
                "columns": ["region", "n"],
            }
        ),
        encoding="utf-8",
    )
    (d / "data.csv").write_text("region,n\nBG411,10\nBG341,\n", encoding="utf-8")
    (d / "dcat.jsonld").write_text(
        json.dumps(
            {
                "@id": f"https://data.health.egov.bg/dataset/{identifier}",
                "@type": "dcat:Dataset",
                "dct:identifier": identifier,
                "dct:title": [{"@value": f"Набор {identifier}", "@language": "bg"}],
                "dcat:theme": [
                    {"@id": "http://publications.europa.eu/resource/authority/data-theme/HEAL"}
                ],
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture()
def snapshots_root(tmp_path: Path) -> Path:
    root = tmp_path / "snapshots"
    _write_snapshot(root, "alpha", "1.0.0", "2024-03-01T09:00:00+02:00")
    _write_snapshot(root, "alpha", "1.1.0", "2024-04-01T09:00:00+02:00")
    _write_snapshot(root, "beta", "1.0.0", "2024-03-15T09:00:00+02:00")
    return root
