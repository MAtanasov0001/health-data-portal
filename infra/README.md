# Инфраструктура (infra)

Режим **B** (IaC). Локална среда чрез Docker Compose и скелет за продукционна инфраструктура
(Terraform/Ansible). Продукцията върви в Държавния хибриден частен облак (ДХЧО) — стекът е
преносим (cloud-agnostic, концепция v2.0, раздел 16).

## Локална среда (демо)

```bash
cd infra
cp .env.example .env          # само локални заместители, без реални тайни
# 1) първо произведи снапшот, за да има какво да поднася API-то:
(cd ../ingestion && pip install -e . && \
   python -m ingestion.pipeline run ../pilot/hospitalizacii-po-oblast-2023 --out snapshots)
# 2) вдигни средата (CKAN прави db init, sysadmin и API токен автоматично):
docker compose up --build -d
# 3) публикувай снапшотите в каталога (след като CKAN е здрав):
docker compose --profile tools run --rm catalog-sync
# 4) провери целия път end-to-end (API → CKAN → frontend):
./smoke.sh
```

`smoke.sh` проверява „златния път" от концепцията: списък → набор → изтегляне (CSV/JSON/XLSX),
DCAT-AP/StatDCAT-AP формати, пагинация (МЕ90), уникален GET адрес (МЕ72) и CKAN-съвместимото
харвестване. При нужда се дават други адреси или се пропускат услуги:
`SKIP_CKAN=1 SKIP_FRONTEND=1 ./smoke.sh` (само API).

Услуги след вдигане:

| Услуга | Адрес | Роля |
|--------|-------|------|
| frontend | http://localhost:3000 | Публичен Next.js сайт |
| api | http://localhost:8000/docs | Публично четящо API (OpenAPI 3.1) |
| ckan | http://localhost:5000 | Каталог (вариант А) + DCAT-AP/харвест |
| catalog-sync | (профил `tools`) | Адаптер снапшот → CKAN (пуска се при поискване) |
| db / redis / solr | вътрешни | Зависимости на CKAN |

Каталогът се пълни от **`catalog-sync`** (адаптер снапшот → CKAN), не автоматично: пуска се
след като CKAN е готов и има произведени снапшоти. Верификация на DCAT-AP/харвест крайните
точки — виж [`../catalog/README.md`](../catalog/README.md).

## Тайни и сигурност

- В това хранилище **няма реални тайни**. `.env.example` съдържа само заместители; `.env` е в
  `.gitignore`. Сканирането за тайни е блокираща CI порта.
- Приложният **доставчик на тайни** (`api/api/security/secrets.py`) вече съществува със seam за
  бъдещ мениджър: по подразбиране чете от околната среда (env бекенд), а продукционното **хранилище
  за тайни** (Vault/AWS/git.egov.bg) е plug-point, който се активира след одит по режим C.
- SSRF-устойчивият **приложен** клиент (`api/api/security/ssrf.py`) също е готов seam (HTTPS-only,
  проверка на IP, пиниране, без redirect). Мрежовото egress-филтриране остава инфраструктурна задача.

## Продукционен скелет (Terraform/Ansible)

`terraform/` съдържа **само скелет** с ясни граници. Мрежовата сегментация, deny-by-default
egress филтрирането, WAF и мрежовият слой на живия proxy са **инфраструктурни** компоненти от
**режим C** и не се разработват в тази фаза (приложните SSRF-контроли обаче вече са налични — виж
по-горе и `docs/security-architecture.md`).
