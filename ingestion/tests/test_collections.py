import json
from pathlib import Path

import pytest

from ingestion.collections import (
    CollectionSpec,
    TableSpec,
    infer_schema,
    run_collection,
)


def test_infer_schema_splits_dimensions_and_measures():
    header = ["region", "count", "per_1000"]
    rows = [["Sofia", "120", "3,5"], ["Plovdiv", "80", "2.1"]]
    dimensions, measures = infer_schema(header, rows)
    assert dimensions == ["region"]
    assert measures == ["count", "per_1000"]


def test_infer_schema_blank_measure_column_is_measure():
    header = ["region", "count"]
    rows = [["Sofia", "120"], ["Plovdiv", ""]]
    dimensions, measures = infer_schema(header, rows)
    assert dimensions == ["region"]
    assert measures == ["count"]


def test_infer_schema_all_text_column_is_dimension():
    header = ["type", "label"]
    rows = [["a", "x"], ["b", "y"]]
    dimensions, measures = infer_schema(header, rows)
    assert dimensions == ["type", "label"]
    assert measures == []


def test_table_spec_rejects_bad_slug():
    with pytest.raises(ValueError):
        TableSpec(file="t.csv", identifier="Po_Vid", title={"bg": "Х"})


def _write_collection(root: Path) -> Path:
    coll = root / "demo"
    (coll / "tables").mkdir(parents=True)
    (coll / "tables" / "po-oblast.csv").write_text(
        "region,count\nSofia,120\nPlovdiv,80\n", encoding="utf-8"
    )
    spec = {
        "identifier": "demo-nzok",
        "title": {"bg": "Демо", "en": "Demo"},
        "description": {"bg": "Описание", "en": "Description"},
        "publisher": "МИДТ",
        "contact_email": "data@health.egov.bg",
        "theme": ["HEAL"],
        "keyword": {"bg": ["демо"]},
        "license": "CC-BY-4.0",
        "version": "1.0.0",
        "tables": [
            {
                "file": "po-oblast.csv",
                "identifier": "po-oblast",
                "title": {"bg": "По област", "en": "By region"},
            }
        ],
    }
    import yaml

    (coll / "collection.yaml").write_text(
        yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8"
    )
    return coll


def test_run_collection_writes_snapshot(tmp_path):
    coll_dir = _write_collection(tmp_path / "src")
    out = tmp_path / "snapshots"
    result = run_collection(coll_dir, out)

    assert result.identifier == "demo-nzok"
    assert len(result.tables) == 1
    table = result.tables[0]
    assert table.identifier == "demo-nzok-po-oblast"
    assert table.row_count == 2
    assert table.dimensions == ["region"]
    assert table.measures == ["count"]

    manifest = json.loads(
        (out / "demo-nzok-po-oblast" / "1.0.0" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["collection"]["id"] == "demo-nzok"
    assert manifest["collection"]["table"] == "po-oblast"
    assert manifest["disclosure_control"]["method"] == "none"
    assert (out / "demo-nzok-po-oblast" / "1.0.0" / "data.csv").exists()
    assert (out / "demo-nzok-po-oblast" / "1.0.0" / "dcat.jsonld").exists()


def test_run_collection_immutable_version(tmp_path):
    coll_dir = _write_collection(tmp_path / "src")
    out = tmp_path / "snapshots"
    run_collection(coll_dir, out)
    with pytest.raises(FileExistsError):
        run_collection(coll_dir, out)


def test_collection_spec_from_yaml(tmp_path):
    coll_dir = _write_collection(tmp_path / "src")
    spec = CollectionSpec.from_yaml(coll_dir / "collection.yaml")
    assert spec.identifier == "demo-nzok"
    assert spec.tables[0].identifier == "po-oblast"
