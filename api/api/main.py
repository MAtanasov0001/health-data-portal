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
import datetime as dt
import io
import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from . import formats
from .repository import DatasetVersion, Repository
from .security import install_security, validate_identifier

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TURTLE_MEDIA_TYPE = "text/turtle; charset=utf-8"
JSONLD_MEDIA_TYPE = "application/ld+json"

API_VERSION = "1.0.0"  # версия на самия интерфейс (чл. 14, ал. 1), различна от версията на данните
API_MAJOR = "v1"
SUPPORT_YEARS = 2  # минимум 24 месеца поддръжка на стара версия (чл. 41, ал. 3; чл. 14, ал. 6)

app = FastAPI(
    title="Портал за отворени данни в здравеопазването — публично API",
    version=API_VERSION,
    description="Четящо API за набори от здравни отворени данни (DCAT-AP, CKAN-съвместимо).",
    openapi_version="3.1.0",
)

BASE_URL = os.environ.get("OHDP_BASE_URL", "https://data.health.egov.bg")


@app.middleware("http")
async def _advertise_api_version(request: Request, call_next: Any) -> Response:
    """Всеки отговор носи версията на интерфейса (чл. 14, ал. 1) в машинночетим хедър."""
    response: Response = await call_next(request)
    response.headers["X-API-Version"] = API_VERSION
    return response


# Пласт за сигурност (режим C): защитни хедъри, CORS, лимити, безопасни грешки.
install_security(app)


def get_repo() -> Repository:
    root = Path(os.environ.get("OHDP_SNAPSHOTS", "../ingestion/snapshots")).resolve()
    return Repository(root)


def _plus_years(iso_ts: str, years: int) -> str:
    """ISO-8601 времеви печат + ``years`` години (за края на гарантираната поддръжка)."""
    base = dt.datetime.fromisoformat(iso_ts)
    try:
        return base.replace(year=base.year + years).isoformat()
    except ValueError:  # 29 февруари в невисокосна година
        return (base + dt.timedelta(days=365 * years)).isoformat()


def _deprecation(dv: DatasetVersion, latest: DatasetVersion | None) -> dict[str, Any] | None:
    """Машинночетимо известие, когато ``dv`` не е най-новата версия (чл. 14, ал. 4)."""
    if latest is None or dv.version == latest.version:
        return None
    return {
        "deprecated": True,
        "requested_version": dv.version,
        "latest_version": latest.version,
        "latest_url": f"{BASE_URL}/{API_MAJOR}/datasets/{dv.identifier}",
        "superseded_at": latest.created_at,
        "sunset": _plus_years(latest.created_at, SUPPORT_YEARS),
        "note": (
            "Заявена е по-стара версия на набора. Поддържа се минимум 24 месеца от издаването "
            "на следващата версия (чл. 41, ал. 3; чл. 14, ал. 6)."
        ),
    }


def _apply_version(
    repo: Repository, dv: DatasetVersion, response: Response
) -> dict[str, Any] | None:
    """Слага версийните/deprecation хедъри и връща машинночетимото известие (или ``None``)."""
    response.headers["X-Dataset-Version"] = dv.version
    latest = repo.latest(dv.identifier)
    info = _deprecation(dv, latest)
    if info is None:
        return None
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = info["sunset"]
    response.headers["Link"] = f'<{info["latest_url"]}>; rel="latest-version"'
    return info


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
        "collection": (dv.collection or {}).get("id"),
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


def _titles_dict(value: Any) -> dict[str, str]:
    """Заглавие от манифеста (обикновен dict bg/en) или от DCAT (списък с @language)."""
    if isinstance(value, dict):
        return {k: str(v) for k, v in value.items()}
    if isinstance(value, list):
        return {t["@language"]: t["@value"] for t in value if "@language" in t}
    return {}


def _collection_group(cid: str, members: list[DatasetVersion]) -> dict[str, Any]:
    """Обобщение на една колекция (група таблици) за списъка ``/v1/collections``."""
    meta = members[0].collection or {}
    themes = sorted(
        {
            t["@id"].rsplit("/", 1)[-1]
            for dv in members
            for t in dv.dcat.get("dcat:theme", [])
        }
    )
    return {
        "id": cid,
        "uri": f"{BASE_URL}/v1/collections/{cid}",
        "title": _titles_dict(meta.get("title")),
        "description": _titles_dict(meta.get("description")),
        "table_count": len(members),
        "total_rows": sum(dv.row_count for dv in members),
        "themes": themes,
        "issued": max((dv.created_at for dv in members), default=""),
    }


def _collection_table(dv: DatasetVersion) -> dict[str, Any]:
    """Един член на колекция — таблица с извлечени измерения/мерки за визуализацията."""
    meta = dv.collection or {}
    return {
        "identifier": dv.identifier,
        "table": meta.get("table"),
        "title": _titles_dict(meta.get("table_title")),
        "row_count": dv.row_count,
        "columns": dv.manifest.get("columns", []),
        "dimensions": dv.dimensions,
        "measures": dv.measures,
    }


@app.get("/v1/collections", tags=["набори"], summary="Списък с колекции (групи таблици)")
def list_collections(repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    """Колекциите са Eurostat-подобни групи от свързани таблици под обща тема."""
    groups = repo.collections()
    items = [_collection_group(cid, members) for cid, members in sorted(groups.items())]
    return {"total": len(items), "items": items}


@app.get(
    "/v1/collections/{collection_id}",
    tags=["набори"],
    summary="Детайл на колекция + нейните таблици",
)
def get_collection(collection_id: str, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    validate_identifier(collection_id)
    members = repo.collection_members(collection_id)
    if not members:
        raise HTTPException(status_code=404, detail=f"Няма колекция '{collection_id}'")
    body = _collection_group(collection_id, members)
    body["tables"] = [_collection_table(dv) for dv in members]
    return body


def _require(repo: Repository, identifier: str, version: str | None) -> DatasetVersion:
    validate_identifier(identifier)
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
    response: Response,
    version: str | None = Query(None, description="Конкретна версия; по подразбиране най-новата"),
    accept: str = Header(default=""),
    repo: Repository = Depends(get_repo),
) -> Response | dict[str, Any]:
    """Детайл на набора. Съдържа договаряне на съдържанието (МЕ34): ``Accept: text/turtle`` →
    RDF/Turtle, ``application/ld+json`` → JSON-LD, иначе — JSON обвивка с DCAT вътре."""
    dv = _require(repo, identifier, version)
    dcat = _enrich_dcat(dv)
    if "text/turtle" in accept:
        out: Response = Response(formats.dataset_to_turtle(dcat), media_type=TURTLE_MEDIA_TYPE)
        _apply_version(repo, dv, out)
        return out
    if "ld+json" in accept:
        out = JSONResponse(dcat, media_type=JSONLD_MEDIA_TYPE)
        _apply_version(repo, dv, out)
        return out
    info = _apply_version(repo, dv, response)
    body = {
        **_summary(dv),
        "checksum_sha256": dv.checksum_sha256,
        "dcat": dcat,
        "distributions": _distributions(dv),
    }
    if info:
        body["deprecation"] = info
    return body


@app.get("/v1/datasets/{identifier}/versions", tags=["набори"], summary="Всички версии на набор")
def list_versions(identifier: str, repo: Repository = Depends(get_repo)) -> dict[str, Any]:
    validate_identifier(identifier)
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
        out = PlainTextResponse(
            dv.data_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"X-Total-Count": str(dv.row_count)},
        )
        _apply_version(repo, dv, out)
        return out
    header, window = dv.data_page((page - 1) * page_size, page_size)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(window)
    out = PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "X-Total-Count": str(dv.row_count),
            "X-Page": str(page),
            "X-Page-Size": str(page_size),
        },
    )
    _apply_version(repo, dv, out)
    return out


@app.get("/v1/datasets/{identifier}/data.json", tags=["данни"])
def data_json(
    identifier: str,
    response: Response,
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
    info = _apply_version(repo, dv, response)
    body: dict[str, Any] = {
        "identifier": dv.identifier,
        "version": dv.version,
        "total": dv.row_count,
        "page": page,
        "page_size": page_size,
        "rows": rows,
    }
    if info:
        body["deprecation"] = info
    return body


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
    out = Response(
        content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{dv.identifier}-{dv.version}.xlsx"',
            "X-Total-Count": str(dv.row_count),
        },
    )
    _apply_version(repo, dv, out)
    return out


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
    out = Response(formats.dataset_to_turtle(_enrich_dcat(dv)), media_type=TURTLE_MEDIA_TYPE)
    _apply_version(repo, dv, out)
    return out


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
    out = JSONResponse(_enrich_dcat(dv), media_type=JSONLD_MEDIA_TYPE)
    _apply_version(repo, dv, out)
    return out


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
    out: Response
    if "text/csv" in accept:
        out = PlainTextResponse(
            dv.data_csv(),
            media_type="text/csv; charset=utf-8",
            headers={"X-Total-Count": str(dv.row_count)},
        )
    elif "spreadsheet" in accept or "ms-excel" in accept:
        rows = dv.iter_data()
        header = next(rows, [])
        out = Response(formats.xlsx_bytes(header, rows), media_type=XLSX_MEDIA_TYPE)
    else:
        out = JSONResponse(
            {"identifier": dv.identifier, "version": dv.version, "download": _distributions(dv)}
        )
    _apply_version(repo, dv, out)
    return out


@app.get(
    "/v1/datasets/{identifier}/summary",
    tags=["данни"],
    summary="Агрегат по измерение (за визуализация)",
)
def data_summary(
    identifier: str,
    response: Response,
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
    info = _apply_version(repo, dv, response)
    body: dict[str, Any] = {
        "identifier": dv.identifier,
        "version": dv.version,
        "dimension": dim,
        "measure": mea,
        "top": top,
        "groups": [{"key": k, "value": v, "count": c} for k, v, c in groups],
    }
    if info:
        body["deprecation"] = info
    return body


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
    validate_identifier(id)
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
