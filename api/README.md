# Публично четящо API

Режим **B**. FastAPI приложение (OpenAPI 3.1), което поднася неизменяемите снапшоти от приемната
тръба. Само за четене — порталът никога не приема данни през това API.

## Нормативни принципи

- **API-first** (чл. 41) — всяка функционалност има публична крайна точка.
- **Версия в пътя** `/v1` (чл. 14); старите версии на данните остават достъпни.
- **GET на уникален адрес** (МЕ72) — справките са GET; всеки ресурс има собствен URI; без POST.
- **Пагинация** (МЕ90) за списъци.
- **Многоформатен експорт** (МЕ34) — CSV, JSON, XLSX и RDF/Turtle, всеки на уникален GET адрес,
  плюс договаряне на съдържанието чрез `Accept`.
- **Интероперативност** — DCAT-AP каталог (JSON-LD и Turtle) + CKAN-съвместими крайни точки за
  харвестване от data.egov.bg и data.europa.eu.
- **Версиониране на интерфейса** (чл. 14, чл. 41) — всеки отговор носи `X-API-Version`; при
  заявка на по-стара версия на набор API-то връща `Deprecation: true`, `Sunset` (краен срок на
  гарантираната поддръжка — минимум 24 месеца от следващата версия) и `Link: rel="latest-version"`,
  плюс машинночетим обект `deprecation` в тялото на JSON справките.

## Крайни точки

| Метод и път | Предназначение |
|-------------|----------------|
| `GET /v1/health` | Проверка на живост |
| `GET /v1/datasets?page=&page_size=` | Пагиниран списък с набори |
| `GET /v1/datasets/{id}` | Детайл на набор; `Accept: text/turtle` / `application/ld+json` → RDF |
| `GET /v1/datasets/{id}/versions` | Всички версии на набор |
| `GET /v1/datasets/{id}/data.csv` | Данни като CSV (по избор `?page=&page_size=`) |
| `GET /v1/datasets/{id}/data.json` | Данни като JSON (пагинирано) |
| `GET /v1/datasets/{id}/data.xlsx` | Данни като XLSX (пълен набор) |
| `GET /v1/datasets/{id}/data` | Данни с договаряне на формат по `Accept` (CSV/XLSX/JSON) |
| `GET /v1/datasets/{id}/dcat.ttl` | Метаданни на набора (RDF/Turtle) |
| `GET /v1/datasets/{id}/dcat.jsonld` | Метаданни на набора (JSON-LD) |
| `GET /v1/datasets/{id}/summary` | Агрегат по измерение (за визуализация) |
| `GET /v1/catalog.jsonld` | DCAT-AP каталог (JSON-LD) |
| `GET /v1/catalog.ttl` | DCAT-AP каталог (RDF/Turtle) |
| `GET /api/3/action/package_list` | CKAN-съвместим списък |
| `GET /api/3/action/package_show?id=` | CKAN-съвместим детайл |

Всяка от дистрибуциите приема по избор `?version=`; по подразбиране — най-новата. XLSX/RDF се
произвеждат само със стандартната библиотека (`api/api/formats.py`) — без външни зависимости.

## Пласт за сигурност (режим C)

`api/api/security/` е инсталиран върху приложението (`install_security`) и е **активен** за всяка
заявка: защитни хедъри (CSP, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, по избор HSTS),
CORS по избор, ограничаване на честотата (per-IP, fail-open, `/v1/health` е изключен), лимит за
размер на тялото (413) и безопасно обработване на грешки (500 с `correlation_id`, без изтичане).
Идентификаторите в пътя минават канонична валидация (обхождане на пътища → 400). Всичко е
конфигурируемо през `OHDP_*` (вж. `docs/security-architecture.md`).

Готови, но **изключени по подразбиране** seam-ове (не са закачени за публични маршрути):
`security/secrets.py` (доставчик на тайни), `auth/` (идентичност + route guard, бекенд `disabled`),
`security/ssrf.py` (SSRF-устойчив клиент за бъдещ харвест/жив proxy). Подлежат на одит преди
активиране (`docs/review-model.md`).

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
