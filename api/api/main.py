"""FastAPI приложение — публично четящо API (OpenAPI 3.1).

Принципи:
- **API-first** (чл. 41): всяка потребителска функционалност има публична крайна точка.
- **Версия** в пътя ``/v1`` (чл. 14); старите версии на данните остават достъпни.
- **GET на уникален адрес** (МЕ72): справките са GET, без POST; всеки ресурс има собствен URI.
- **Пагинация** (МЕ90) за дълги списъци.
- **Интероперативност**: DCAT/JSON-LD каталог + CKAN-съвместими крайни точки за харвестване.
"""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from . import formats
from .repository import DatasetVersion, Repository

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TURTLE_MEDIA_TYPE = "text/turtle; charset=utf-8"
JSONLD_MEDIA_TYPE = "application/ld+json"

app = FastAPI(
    title="Портал за отворени данни в здравеопазването — публично API",
    version="1.0.0",
    description="Четящо API за набори от здравни отворени данни (DCAT-AP, CKAN-съвместимо).",
    openapi_version="3.1.0",
)

BASE_URL = os.environ.get("OHDP_BASE_URL", "https://data.health.egov.bg")


def get_repo() -> Repository:
    root = Path(os.environ.get("OHDP_SNAPSHOTS", "../ingestion/snapshots")).resolve()
    return Repository(root)


def _titles(dcat: dict[str, Any]) -> dict[str, str]:
    return {t["@language"]: t["@value"] for t in dcat.get("dct:title", []) if "@language" in t}


def _summary(dv: DatasetVersion) -> dict[str, Any]:
    dcat = dv.dcat
    return {
        "identifier": dv.identifier,
        "uri": f"{BASE_URL}/v1/datasets/{dv.identifier}",
        "title": _titles(dcat),
        "version": dv.version,
        "issued": dv.created_at,
        "row_count": dv.row_count,
        "themes": [t["@id"].rsplit("/", 1)[-1] for t in dcat.get("dcat:theme", [])],
    }


def _distributions(dv: DatasetVersion) -> dict[str, str]:
    """Публичните дистрибуции на набора — по един уникален GET адрес на формат (МЕ34/МЕ72)."""
    base = f"{BASE_URL}/v1/datasets/{dv.identifier}"
    return {
        "csv": f"{base}/data.csv",
        "json": f"{base}/data.json",
        "xlsx": f"{base}/data.xlsx",
        "rdf": f"{base}/dcat.ttl",
    }


# file-type речник (Publications Office) за DCAT дистрибуциите
_FILE_TYPE = "http://publications.europa.eu/resource/authority/file-type/"
_DIST_FORMATS = [
    ("data.csv", "CSV", "text/csv"),
    ("data.json", "JSON", "application/json"),
    ("data.xlsx", "XLSX", XLSX_MEDIA_TYPE),
    ("dcat.ttl", "RDF_TURTLE", "text/turtle"),
]


def _enrich_dcat(dv: DatasetVersion) -> dict[str, Any]:
    """Връща DCAT записа от снапшота, допълнен с дистрибуции за всички формати (МЕ34).

    Снапшотите са неизменяеми и носят само CSV дистрибуцията от момента на приемане; API-то е
    презентационният слой и добавя останалите формати при поднасяне, без да пипа снапшота.
    """
    dcat = dict(dv.dcat)
    ds_uri = f"{BASE_URL}/api/v1/datasets/{dv.identifier}"
    existing = dcat.get("dcat:distribution", [])
    present = {d.get("dct:format", {}).get("@id", "") for d in existing if isinstance(d, dict)}
    extra: list[dict[str, Any]] = []
    for path, ftype, media in _DIST_FORMATS:
        fid = _FILE_TYPE + ftype
        if fid in present:
            continue
        extra.append(
            {
                "@type": "dcat:Distribution",
                "@id": f"{ds_uri}/{path}",
                "dcat:accessURL": {"@id": f"{ds_uri}/{path}"},
                "dcat:downloadURL": {"@id": f"{ds_uri}/{path}"},
                "dcat:mediaType": media,
                "dct:format": {"@id": fid},
            }
        )
    if extra:
        dcat["dcat:distribution"] = [*existing, *extra]
    return dcat


@app.get("/v1/health", tags=["служебни"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/datasets", tags=["набори"], summary="Списък с набори (пагиниран)")
def list_datasets(
    page: int = Query(1, ge=1, description="Номер на страница (МЕ90)"),
    page_size: int = Query(20, ge=1, le=100, description="Размер на страница (макс. 100)"),
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    items = repo.list_latest()
    total = len(items)
    start = (page - 1) * page_size
    window = items[start : start + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_summary(dv) for dv in window],
    }


def _require(repo: Repository, identifier: str, version: str | None) -> DatasetVersion:
    dv = repo.get(identifier, version)
    if dv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Няма набор '{identifier}'" + (f" версия '{version}'" if version else ""),
        )
    return dv


@app.get(
    "/v1/datasets/{identifier}",
    tags=["набори"],
    summary="Детайл на набор (DCAT-AP)",
    response_model=None,
)
def get_dataset(
    identifier: str,
    version: str | None = Query(None, description="Конкретна версия; по подразбиране най-новата"),
    accept: str = Header(default=""),
    repo: Repository = Depends(get_repo),
) -> Response | dict[str, Any]:
    """Детайл на набора. Съдържа договаряне на съдържанието (МЕ34): ``Accept: text/turtle`` →
    RDF/Turtle, ``application/ld+json`` → JSON-LD, иначе — JSON обвивка с DCAT вътре."""
    dv = _require(repo, identifier, version)
    dcat = _enrich_dcat(dv)
    if "text/turtle" in accept:
        return Response(formats.dataset_to_turtle(dcat), media_type=TURTLE_MEDIA_TYPE)
    if "ld+json" in accept:
        return JSONResponse(dcat, media_type=JSONLD_MEDIA_TYPE)
    return {
        **_summary(dv),
        "checksum_sha256": dv.checksum_sha256,
        "dcat": dcat,
        "distributions": _distributions(dv),
    }


@app.get("/v1/datasets/{identifier}/versions", tags=["набори"], summary="Всички версии на набор")
def list_versions(identifier: str, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    versions = repo._versions(identifier)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Няма набор '{identifier}'")
    return {
        "identifier": identifier,
        "versions": [
            {"version": dv.version, "issued": dv.created_at, "checksum_sha256": dv.checksum_sha256}
            for dv in versions
        ],
    }


@app.get("/v1/datasets/{identifier}/data.csv", tags=["данни"], response_class=PlainTextResponse)
def data_csv(
    identifier: str,
    version: str | None = Query(None),
    page: int | None = Query(None, ge=1, description="Страница; без нея се връща целият файл"),
    page_size: int = Query(1000, ge=1, le=10000, description="Размер на страница (макс. 10000)"),
    repo: Repository = Depends(get_repo),
) -> Response:
    dv = _require(repo, identifier, version)
    if page is None:  # пълен обемен файл (CSV дистрибуцията по DCAT е целият набор)
        return PlainTextResponse(
            dv.data_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"X-Total-Count": str(dv.row_count)},
        )
    header, window = dv.data_page((page - 1) * page_size, page_size)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(window)
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "X-Total-Count": str(dv.row_count),
            "X-Page": str(page),
            "X-Page-Size": str(page_size),
        },
    )


@app.get("/v1/datasets/{identifier}/data.json", tags=["данни"])
def data_json(
    identifier: str,
    version: str | None = Query(None),
    page: int = Query(1, ge=1, description="Номер на страница (МЕ90)"),
    page_size: int = Query(100, ge=1, le=1000, description="Размер на страница (макс. 1000)"),
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    dv = _require(repo, identifier, version)
    header, window = dv.data_page((page - 1) * page_size, page_size)
    rows = [
        {k: (None if v == "" else v) for k, v in zip(header, values, strict=False)}
        for values in window
    ]
    return {
        "identifier": dv.identifier,
        "version": dv.version,
        "total": dv.row_count,
        "page": page,
        "page_size": page_size,
        "rows": rows,
    }


@app.get("/v1/datasets/{identifier}/data.xlsx", tags=["данни"], summary="Дистрибуция XLSX (МЕ34)")
def data_xlsx(
    identifier: str,
    version: str | None = Query(None),
    repo: Repository = Depends(get_repo),
) -> Response:
    dv = _require(repo, identifier, version)
    rows = dv.iter_data()
    header = next(rows, [])
    content = formats.xlsx_bytes(header, rows)
    return Response(
        content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{dv.identifier}-{dv.version}.xlsx"',
            "X-Total-Count": str(dv.row_count),
        },
    )


@app.get(
    "/v1/datasets/{identifier}/dcat.ttl",
    tags=["интероперативност"],
    summary="Метаданни (RDF/Turtle)",
)
def dataset_ttl(
    identifier: str,
    version: str | None = Query(None),
    repo: Repository = Depends(get_repo),
) -> Response:
    dv = _require(repo, identifier, version)
    return Response(formats.dataset_to_turtle(_enrich_dcat(dv)), media_type=TURTLE_MEDIA_TYPE)


@app.get(
    "/v1/datasets/{identifier}/dcat.jsonld",
    tags=["интероперативност"],
    summary="Метаданни (JSON-LD)",
)
def dataset_jsonld(
    identifier: str,
    version: str | None = Query(None),
    repo: Repository = Depends(get_repo),
) -> JSONResponse:
    dv = _require(repo, identifier, version)
    return JSONResponse(_enrich_dcat(dv), media_type=JSONLD_MEDIA_TYPE)


@app.get(
    "/v1/datasets/{identifier}/data", tags=["данни"], summary="Данни с договаряне на формат (МЕ34)"
)
def data_negotiated(
    identifier: str,
    version: str | None = Query(None),
    accept: str = Header(default=""),
    repo: Repository = Depends(get_repo),
) -> Response:
    """Един адрес, много формати: ``Accept`` избира CSV, XLSX или JSON (по подр. JSON)."""
    dv = _require(repo, identifier, version)
    if "text/csv" in accept:
        return PlainTextResponse(
            dv.data_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"X-Total-Count": str(dv.row_count)},
        )
    if "spreadsheet" in accept or "ms-excel" in accept:
        rows = dv.iter_data()
        header = next(rows, [])
        return Response(formats.xlsx_bytes(header, rows), media_type=XLSX_MEDIA_TYPE)
    return JSONResponse(
        {"identifier": dv.identifier, "version": dv.version, "download": _distributions(dv)}
    )


@app.get(
    "/v1/datasets/{identifier}/summary",
    tags=["данни"],
    summary="Агрегат по измерение (за визуализация)",
)
def data_summary(
    identifier: str,
    dimension: str | None = Query(None, description="Категорийна колона; по подр. първата"),
    measure: str | None = Query(None, description="Числова колона; по подр. последната"),
    top: int = Query(10, ge=1, le=50, description="Брой групи (топ по стойност)"),
    version: str | None = Query(None),
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    dv = _require(repo, identifier, version)
    columns: list[str] = dv.manifest["columns"]
    dim = dimension or columns[0]
    mea = measure or columns[-1]
    for name in (dim, mea):
        if name not in columns:
            raise HTTPException(status_code=400, detail=f"Няма колона '{name}' в набора")
    groups = dv.aggregate(dim, mea, top)
    return {
        "identifier": dv.identifier,
        "version": dv.version,
        "dimension": dim,
        "measure": mea,
        "top": top,
        "groups": [{"key": k, "value": v, "count": c} for k, v, c in groups],
    }


_CATALOG_TITLE_BG = "Портал за отворени данни в здравеопазването"
_CATALOG_TITLE_EN = "Open Health Data Portal"
_CATALOG_PUBLISHER = "МИДТ"


@app.get("/v1/catalog.jsonld", tags=["интероперативност"], summary="DCAT-AP каталог (JSON-LD)")
def catalog(repo: Repository = Depends(get_repo)) -> JSONResponse:
    datasets = [_enrich_dcat(dv) for dv in repo.list_latest()]
    doc = {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
        },
        "@type": "dcat:Catalog",
        "dct:title": [
            {"@value": _CATALOG_TITLE_BG, "@language": "bg"},
            {"@value": _CATALOG_TITLE_EN, "@language": "en"},
        ],
        "dct:publisher": {"@type": "foaf:Agent", "foaf:name": _CATALOG_PUBLISHER},
        "dcat:dataset": datasets,
    }
    return JSONResponse(doc, media_type=JSONLD_MEDIA_TYPE)


@app.get("/v1/catalog.ttl", tags=["интероперативност"], summary="DCAT-AP каталог (RDF/Turtle)")
def catalog_ttl(repo: Repository = Depends(get_repo)) -> Response:
    datasets = [_enrich_dcat(dv) for dv in repo.list_latest()]
    body = formats.catalog_to_turtle(
        datasets,
        base=BASE_URL,
        title_bg=_CATALOG_TITLE_BG,
        title_en=_CATALOG_TITLE_EN,
        publisher=_CATALOG_PUBLISHER,
    )
    return Response(body, media_type=TURTLE_MEDIA_TYPE)


# --- CKAN-съвместими крайни точки (за харвестване от data.egov.bg / data.europa.eu) ---


@app.get("/api/3/action/package_list", tags=["интероперативност"], summary="CKAN package_list")
def ckan_package_list(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    return {"success": True, "result": repo.identifiers()}


@app.get("/api/3/action/package_show", tags=["интероперативност"], summary="CKAN package_show")
def ckan_package_show(
    id: str = Query(..., description="Идентификатор на набора"),
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    dv = repo.latest(id)
    if dv is None:
        raise HTTPException(status_code=404, detail=f"Няма набор '{id}'")
    titles = _titles(dv.dcat)
    return {
        "success": True,
        "result": {
            "name": dv.identifier,
            "title": titles.get("bg") or next(iter(titles.values()), dv.identifier),
            "version": dv.version,
            "metadata_modified": dv.created_at,
            "resources": [
                {"format": "CSV", "url": f"{BASE_URL}/v1/datasets/{dv.identifier}/data.csv"},
                {"format": "JSON", "url": f"{BASE_URL}/v1/datasets/{dv.identifier}/data.json"},
                {"format": "XLSX", "url": f"{BASE_URL}/v1/datasets/{dv.identifier}/data.xlsx"},
                {"format": "RDF", "url": f"{BASE_URL}/v1/datasets/{dv.identifier}/dcat.ttl"},
            ],
        },
    }
