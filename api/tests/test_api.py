import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402


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


def test_list_filter_by_query(client: TestClient):
    body = client.get("/v1/datasets", params={"q": "beta"}).json()
    ids = [d["identifier"] for d in body["items"]]
    assert ids == ["beta"]
    assert body["total"] == 1


def test_list_filter_by_query_is_case_insensitive(client: TestClient):
    body = client.get("/v1/datasets", params={"q": "ALPHA"}).json()
    assert [d["identifier"] for d in body["items"]] == ["alpha"]


def test_list_filter_by_theme(client: TestClient):
    body = client.get("/v1/datasets", params={"theme": "HEAL"}).json()
    assert body["total"] == 2
    assert client.get("/v1/datasets", params={"theme": "EDUC"}).json()["total"] == 0


def test_list_filter_unknown_query_is_empty(client: TestClient):
    body = client.get("/v1/datasets", params={"q": "zzz-nomatch"}).json()
    assert body["items"] == []
    assert body["total"] == 0


def test_catalog_csv_distribution_has_bytesize_and_checksum(client: TestClient):
    ds = client.get("/v1/catalog.jsonld").json()["dcat:dataset"][0]
    csv_dist = next(
        d
        for d in ds["dcat:distribution"]
        if d["dct:format"]["@id"].endswith("/CSV")
    )
    assert csv_dist["dcat:byteSize"] > 0
    assert csv_dist["spdx:checksum"]["spdx:checksumValue"] == "a" * 64


def test_catalog_advertises_data_service(client: TestClient):
    service = client.get("/v1/catalog.jsonld").json()["dcat:service"]
    assert service[0]["@type"] == "dcat:DataService"
    assert service[0]["dcat:endpointDescription"]["@id"].endswith("/openapi.json")


def test_dataset_detail_lists_all_formats(client: TestClient):
    dists = client.get("/v1/datasets/alpha").json()["distributions"]
    assert set(dists) == {"csv", "json", "xlsx", "rdf"}


def test_data_xlsx_is_a_valid_zip(client: TestClient):
    import io
    import zipfile

    r = client.get("/v1/datasets/alpha/data.xlsx")
    assert r.headers["content-type"].startswith(main.XLSX_MEDIA_TYPE)
    assert r.headers["X-Total-Count"] == "2"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        assert "xl/worksheets/sheet1.xml" in names
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "<v>10</v>" in sheet  # числовата клетка е записана като число
    assert "BG411" in sheet


def test_dataset_turtle_via_accept(client: TestClient):
    r = client.get("/v1/datasets/alpha", headers={"Accept": "text/turtle"})
    assert r.headers["content-type"].startswith("text/turtle")
    assert "@prefix dcat:" in r.text
    assert "a dcat:Dataset" in r.text


def test_dataset_jsonld_via_accept(client: TestClient):
    r = client.get("/v1/datasets/alpha", headers={"Accept": "application/ld+json"})
    assert r.headers["content-type"].startswith("application/ld+json")
    assert r.json()["@type"] == "dcat:Dataset"


def test_dataset_ttl_endpoint(client: TestClient):
    r = client.get("/v1/datasets/alpha/dcat.ttl")
    assert r.headers["content-type"].startswith("text/turtle")
    assert "dcat:distribution" in r.text


def test_data_negotiation_csv(client: TestClient):
    r = client.get("/v1/datasets/alpha/data", headers={"Accept": "text/csv"})
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0] == "region,n"


def test_catalog_ttl(client: TestClient):
    r = client.get("/v1/catalog.ttl")
    assert r.headers["content-type"].startswith("text/turtle")
    assert "a dcat:Catalog" in r.text
    assert r.text.count("a dcat:Dataset") == 2


def test_api_version_header_on_every_response(client: TestClient):
    for path in ("/v1/health", "/v1/datasets", "/v1/datasets/alpha"):
        assert client.get(path).headers["X-API-Version"] == main.API_VERSION


def test_latest_version_is_not_deprecated(client: TestClient):
    r = client.get("/v1/datasets/alpha")  # най-новата (1.1.0)
    assert r.headers["X-Dataset-Version"] == "1.1.0"
    assert "Deprecation" not in r.headers
    assert "deprecation" not in r.json()


def test_old_version_is_deprecated_with_headers(client: TestClient):
    r = client.get("/v1/datasets/alpha", params={"version": "1.0.0"})
    assert r.headers["X-Dataset-Version"] == "1.0.0"
    assert r.headers["Deprecation"] == "true"
    assert r.headers["Sunset"]  # ISO краен срок на поддръжка (24 мес.)
    assert 'rel="latest-version"' in r.headers["Link"]


def test_old_version_deprecation_body(client: TestClient):
    body = client.get("/v1/datasets/alpha", params={"version": "1.0.0"}).json()
    dep = body["deprecation"]
    assert dep["deprecated"] is True
    assert dep["requested_version"] == "1.0.0"
    assert dep["latest_version"] == "1.1.0"
    assert dep["latest_url"].endswith("/v1/datasets/alpha")


def test_sunset_is_24_months_after_supersede(client: TestClient):
    import datetime as dt

    body = client.get("/v1/datasets/alpha", params={"version": "1.0.0"}).json()
    dep = body["deprecation"]
    superseded = dt.datetime.fromisoformat(dep["superseded_at"])
    sunset = dt.datetime.fromisoformat(dep["sunset"])
    assert sunset.year - superseded.year == main.SUPPORT_YEARS


def test_data_json_old_version_deprecation(client: TestClient):
    r = client.get("/v1/datasets/alpha/data.json", params={"version": "1.0.0"})
    assert r.headers["Deprecation"] == "true"
    assert r.json()["deprecation"]["latest_version"] == "1.1.0"
