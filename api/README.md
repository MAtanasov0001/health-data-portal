# Публично четящо API

Режим **B**. FastAPI приложение (OpenAPI 3.1), което поднася неизменяемите снапшоти от приемната
тръба. Само за четене — порталът никога не приема данни през това API.

## Нормативни принципи

- **API-first** (чл. 41) — всяка функционалност има публична крайна точка.
- **Версия в пътя** `/v1` (чл. 14); старите версии на данните остават достъпни.
- **GET на уникален адрес** (МЕ72) — справките са GET; всеки ресурс има собствен URI; без POST.
- **Пагинация** (МЕ90) за списъци.
- **Интероперативност** — DCAT-AP каталог (JSON-LD) + CKAN-съвместими крайни точки за харвестване
  от data.egov.bg и data.europa.eu.

## Крайни точки

| Метод и път | Предназначение |
|-------------|----------------|
| `GET /v1/health` | Проверка на живост |
| `GET /v1/datasets?page=&page_size=` | Пагиниран списък с набори |
| `GET /v1/datasets/{id}` | Детайл (DCAT-AP) на набор |
| `GET /v1/datasets/{id}/versions` | Всички версии на набор |
| `GET /v1/datasets/{id}/data.csv` | Данни като CSV |
| `GET /v1/datasets/{id}/data.json` | Данни като JSON |
| `GET /v1/catalog.jsonld` | DCAT-AP каталог (JSON-LD) |
| `GET /api/3/action/package_list` | CKAN-съвместим списък |
| `GET /api/3/action/package_show?id=` | CKAN-съвместим детайл |

Всяка от `data.csv` / `data.json` приема по избор `?version=`; по подразбиране — най-новата.

## Стартиране

```bash
pip install -e ".[dev]"
# Посочи откъде да чете снапшотите (по подразбиране ../ingestion/snapshots):
export OHDP_SNAPSHOTS=../ingestion/snapshots
uvicorn api.main:app --reload
# OpenAPI: http://127.0.0.1:8000/docs   ·   схема: /openapi.json
```

## Тестове

```bash
pytest -q
ruff check . && ruff format --check .
mypy api
```
