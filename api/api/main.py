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

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from .repository import DatasetVersion, Repository

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


@app.get("/v1/datasets/{identifier}", tags=["набори"], summary="Детайл на набор (DCAT-AP)")
def get_dataset(
    identifier: str,
    version: str | None = Query(None, description="Конкретна версия; по подразбиране най-новата"),
    repo: Repository = Depends(get_repo),
) -> dict[str, Any]:
    dv = _require(repo, identifier, version)
    return {
        **_summary(dv),
        "checksum_sha256": dv.checksum_sha256,
        "dcat": dv.dcat,
        "distributions": {
            "csv": f"{BASE_URL}/v1/datasets/{dv.identifier}/data.csv",
            "json": f"{BASE_URL}/v1/datasets/{dv.identifier}/data.json",
        },
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


@app.get("/v1/catalog.jsonld", tags=["интероперативност"], summary="DCAT-AP каталог (JSON-LD)")
def catalog(repo: Repository = Depends(get_repo)) -> JSONResponse:
    datasets = [dv.dcat for dv in repo.list_latest()]
    doc = {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "dct": "http://purl.org/dc/terms/",
            "foaf": "http://xmlns.com/foaf/0.1/",
        },
        "@type": "dcat:Catalog",
        "dct:title": [
            {"@value": "Портал за отворени данни в здравеопазването", "@language": "bg"},
            {"@value": "Open Health Data Portal", "@language": "en"},
        ],
        "dct:publisher": {"@type": "foaf:Agent", "foaf:name": "МИДТ"},
        "dcat:dataset": datasets,
    }
    return JSONResponse(doc, media_type="application/ld+json")


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
            ],
        },
    }
