# Каталог — CKAN (вариант А)

Каталожното ядро е **CKAN** (концепция v2.0, раздел 16.1: *вариант А — CKAN като ядро +
изцяло собствен frontend*). CKAN е зряло, DCAT-AP-native решение, използвано и от
data.egov.bg — това дава оперативна съвместимост и харвестване „наготово“, без да пишем
чувствителен каталожен код.

## Роля в архитектурата

```
приемане → неизменяем снапшот → CKAN (каталог/метаданни) ─┐
                                                           ├─→ публично API (наш) → frontend (наш)
                              DCAT-AP / CKAN харвест ───────┘
```

- **CKAN** държи метаданните и осигурява DCAT-AP / CKAN-съвместими крайни точки за
  харвестване (`ckanext-dcat`).
- **Нашето API** (`/api`) поднася данните на снапшотите и огледално CKAN-съвместими справки.
- **Нашият frontend** (`/frontend`) е изцяло собствен — не използваме вградения UI на CKAN.

## Съдържание

| Път | Роля |
|-----|------|
| `ckan/Dockerfile` | CKAN 2.10 + `ckanext-dcat` (фиксирана версия) |
| `ckan/docker-entrypoint.d/10_bootstrap.sh` | db init, sysadmin, API токен (идемпотентно) |
| `sync/ckan_sync.py` | адаптер снапшот → CKAN (виж [`sync/README.md`](sync/README.md)) |

## Пускане и верификация (изисква Docker)

CKAN се вдига от `infra/docker-compose.yml`. Пълните стъпки са в
[`../infra/README.md`](../infra/README.md); накратко:

```bash
cd infra
cp .env.example .env          # само локални заместители, без реални тайни

# 1) произведи снапшот (за да има какво да публикуваме в каталога)
(cd ../ingestion && pip install -e . && \
   python -m ingestion.pipeline run ../pilot/hospitalizacii-po-oblast-2023 --out snapshots)

# 2) вдигни средата (CKAN прави db init, sysadmin и API токен автоматично)
docker compose up --build -d

# 3) изчакай CKAN да е здрав, после публикувай снапшотите в каталога
docker compose --profile tools run --rm catalog-sync
```

Проверка, че CKAN е каталог на записа:

```bash
# CKAN връща публикувания набор
curl "http://localhost:5000/api/3/action/package_list"

# DCAT-AP каталог (за харвестване от data.egov.bg / data.europa.eu)
curl "http://localhost:5000/catalog.jsonld"
curl "http://localhost:5000/catalog.xml"

# Набор в DCAT-AP
curl "http://localhost:5000/dataset/hospitalizacii-po-oblast-2023.jsonld"
```

Frontend страницата „Документация“ линква към горните CKAN/DCAT крайни точки
(`OHDP_CKAN_URL`).

> Забележка: тази среда е **режим B** и не може да се верифицира без Docker хост. В средата
> на разработка без Docker се верифицира само тръбата ingestion → API → frontend (виж
> кореновия README).

## Граница на режима

Настройката на CKAN (метаданни, харвест профили) е **режим B**. Всичко около идентичност,
автентикация и интеграция с продукционни системи на титуляри е **режим C** — извън тази фаза.
