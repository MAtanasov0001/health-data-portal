# Адаптер снапшот → CKAN

`ckan_sync.py` публикува неизменяемите снапшоти от приемната тръба като набори
(packages) в CKAN. Само стандартна библиотека, **идемпотентен** (създава или обновява),
**режим B** (само метаданни).

## Какво прави

За най-новата версия на всеки набор в `OHDP_SNAPSHOTS`:

1. осигурява организация-собственик (`CKAN_ORG`, по подр. `midt`);
2. чете `manifest.json` + `dcat.jsonld` от снапшота;
3. upsert-ва CKAN package (по `name` = `identifier`) с ресурси, сочещи към данните в
   нашето публично API.

## Съответствие на полетата (снапшот → CKAN → DCAT-AP)

| Снапшот / DCAT | CKAN package | DCAT-AP изход (ckanext-dcat) |
|----------------|--------------|------------------------------|
| `identifier` | `name`, extra `identifier` | `dct:identifier` |
| `dct:title` (bg) | `title` | `dct:title` |
| `dct:description` (bg) | `notes` | `dct:description` |
| `version` | `version` | `owl:versionInfo` |
| `dcat:keyword` | `tags` | `dcat:keyword` |
| `dcat:theme` | extra `theme` | `dcat:theme` |
| `dct:spatial` | extra `spatial_uri` | `dct:spatial` |
| `dct:license` | `license_id` (`cc-by`) | `dct:license` |
| `created_at` | extra `issued` / `modified` | `dct:issued` / `dct:modified` |
| `checksum_sha256` | extra `checksum_sha256` | `spdx:checksum` (по разширение) |
| `disclosureControl` | extra `disclosure_method` / `..._min_cell_size` | (собствено) |
| data.csv / data.json | `resources` (→ нашето API) | `dcat:distribution` |

## Пускане

Обикновено се пуска като услуга от compose (виж `../README.md`):

```bash
docker compose --profile tools run --rm catalog-sync
```

Или директно (стандартна библиотека, без инсталация):

```bash
export CKAN_URL=http://localhost:5000
export CKAN_API_TOKEN=<токен>          # или CKAN_API_TOKEN_FILE
export OHDP_SNAPSHOTS=../../ingestion/snapshots
export OHDP_API_BASE=http://localhost:8000
python ckan_sync.py
```

## Граница на режима

Метаданните и публикуването в каталога са **режим B**. Идентичност, автентикация и
интеграция с продукционни системи на титуляри са **режим C** — извън тази фаза.
