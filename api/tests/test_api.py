from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402
from api.repository import Repository  # noqa: E402


@pytest.fixture()
def client(snapshots_root: Path):
    main.app.dependency_overrides[main.get_repo] = lambda: Repository(snapshots_root)
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_health(client: TestClient):
    assert client.get("/v1/health").json() == {"status": "ok"}


def test_list_paginated(client: TestClient):
    r = client.get("/v1/datasets", params={"page": 1, "page_size": 1})
    body = r.json()
    assert body["total"] == 2
    assert body["page_size"] == 1
    assert len(body["items"]) == 1


def test_dataset_detail_latest(client: TestClient):
    body = client.get("/v1/datasets/alpha").json()
    assert body["version"] == "1.1.0"
    assert body["title"]["bg"].startswith("Набор")
    assert "csv" in body["distributions"]


def test_dataset_specific_version(client: TestClient):
    body = client.get("/v1/datasets/alpha", params={"version": "1.0.0"}).json()
    assert body["version"] == "1.0.0"


def test_missing_dataset_404(client: TestClient):
    assert client.get("/v1/datasets/nope").status_code == 404


def test_data_json_nulls_suppressed(client: TestClient):
    rows = client.get("/v1/datasets/alpha/data.json").json()["rows"]
    assert rows[1]["n"] is None  # потисната клетка → null


def test_data_csv_media_type(client: TestClient):
    r = client.get("/v1/datasets/alpha/data.csv")
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["X-Total-Count"] == "2"  # пълен файл → общ брой в хедъра


def test_data_json_paginated(client: TestClient):
    body = client.get("/v1/datasets/alpha/data.json?page=2&page_size=1").json()
    assert body["total"] == 2
    assert body["page"] == 2
    assert body["page_size"] == 1
    assert len(body["rows"]) == 1
    assert body["rows"][0]["region"] == "BG341"  # вторият ред (offset=1)


def test_data_csv_paginated_window(client: TestClient):
    r = client.get("/v1/datasets/alpha/data.csv?page=1&page_size=1")
    lines = r.text.strip().splitlines()
    assert lines[0] == "region,n"  # хедърът винаги присъства
    assert lines[1].startswith("BG411")  # само първият ред от прозореца
    assert len(lines) == 2
    assert r.headers["X-Page"] == "1"


def test_summary_aggregates_and_skips_suppressed(client: TestClient):
    body = client.get("/v1/datasets/alpha/summary").json()
    assert body["dimension"] == "region"  # по подразбиране първата колона
    assert body["measure"] == "n"  # по подразбиране последната колона
    # BG411,10 → 10; BG341 е потисната (празна) → изключена от агрегата.
    assert body["groups"] == [{"key": "BG411", "value": 10.0, "count": 1}]


def test_summary_unknown_column_400(client: TestClient):
    assert client.get("/v1/datasets/alpha/summary?measure=nope").status_code == 400


def test_ckan_package_list(client: TestClient):
    body = client.get("/api/3/action/package_list").json()
    assert body["success"] is True
    assert body["result"] == ["alpha", "beta"]


def test_catalog_jsonld(client: TestClient):
    r = client.get("/v1/catalog.jsonld")
    assert r.headers["content-type"].startswith("application/ld+json")
    assert len(r.json()["dcat:dataset"]) == 2
