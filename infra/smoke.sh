#!/usr/bin/env bash
# Проверка (smoke test) на локалната среда end-to-end: API → CKAN → frontend.
#
# Пуска се СЛЕД `docker compose up --build -d` и `catalog-sync`. Проверява „златния
# път" от концепцията: списък → филтър → набор → изтегляне → API формати + пагинация
# (МЕ90), уникален GET адрес (МЕ72), DCAT-AP/StatDCAT-AP и CKAN-съвместимо харвестване.
#
# Употреба:
#   infra/smoke.sh                 # подразбиращи се адреси (compose)
#   API_URL=... CKAN_URL=... FRONTEND_URL=... DATASET=... infra/smoke.sh
#   SKIP_CKAN=1 SKIP_FRONTEND=1 infra/smoke.sh   # само API (напр. без вдигнат CKAN)
set -uo pipefail

API_URL="${API_URL:-http://localhost:8000}"
CKAN_URL="${CKAN_URL:-http://localhost:5000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
DATASET="${DATASET:-hospitalizacii-po-oblast-2023}"

pass=0
fail=0

# check <описание> <curl-аргументи...> -- <grep-израз|"">
# Успех = HTTP 2xx И (ако е даден grep-израз) търсеният текст присъства в тялото.
check() {
  local desc="$1"; shift
  local expect=""
  local args=()
  while [ $# -gt 0 ]; do
    if [ "$1" = "--" ]; then shift; expect="$1"; shift; continue; fi
    args+=("$1"); shift
  done
  local body code
  body="$(curl -sS -m 20 -w $'\n%{http_code}' "${args[@]}" 2>/dev/null)"
  code="${body##*$'\n'}"
  body="${body%$'\n'*}"
  if [[ ! "$code" =~ ^2 ]]; then
    printf '  ✗ %s — HTTP %s\n' "$desc" "$code"; fail=$((fail + 1)); return
  fi
  if [ -n "$expect" ] && ! grep -qE "$expect" <<<"$body"; then
    printf '  ✗ %s — липсва „%s" в отговора\n' "$desc" "$expect"; fail=$((fail + 1)); return
  fi
  printf '  ✓ %s\n' "$desc"; pass=$((pass + 1))
}

echo "== API ($API_URL) =="
check "health"                       "$API_URL/v1/health"                                   -- '"?status"?'
check "списък с набори (МЕ90)"        "$API_URL/v1/datasets?page_size=2"                      -- '"page_size":\s*2'
check "детайл на набор (МЕ72)"        "$API_URL/v1/datasets/$DATASET"                         -- "$DATASET"
check "версии на набор"              "$API_URL/v1/datasets/$DATASET/versions"                -- '1\.0\.0'
check "изтегляне CSV"                "$API_URL/v1/datasets/$DATASET/data.csv"                -- ','
check "изтегляне JSON"               "$API_URL/v1/datasets/$DATASET/data.json"               -- '\['
check "изтегляне XLSX"               -o /dev/null "$API_URL/v1/datasets/$DATASET/data.xlsx"  -- ''
check "DCAT-AP (JSON-LD)"            -H 'Accept: application/ld+json' "$API_URL/v1/datasets/$DATASET" -- '"@type"'
check "StatDCAT-AP (Turtle)"         -H 'Accept: text/turtle' "$API_URL/v1/datasets/$DATASET" -- 'stat:numSeries'
check "DCAT-AP каталог (JSON-LD)"    "$API_URL/v1/catalog.jsonld"                            -- 'dcat:'
check "DCAT-AP каталог (Turtle)"     "$API_URL/v1/catalog.ttl"                               -- '@prefix'
check "CKAN-съвместим package_list"  "$API_URL/api/3/action/package_list"                    -- '"success":\s*true'

if [ "${SKIP_CKAN:-0}" != "1" ]; then
  echo "== CKAN ($CKAN_URL) — каталожно ядро =="
  check "status_show"                "$CKAN_URL/api/3/action/status_show"                    -- '"success":\s*true'
  check "package_list съдържа набора" "$CKAN_URL/api/3/action/package_list"                   -- "$DATASET"
  check "DCAT-AP каталог за харвест"  "$CKAN_URL/catalog.jsonld"                              -- 'dcat:'
fi

if [ "${SKIP_FRONTEND:-0}" != "1" ]; then
  echo "== Frontend ($FRONTEND_URL) =="
  check "начална страница"           -o /dev/null "$FRONTEND_URL/"                            -- ''
fi

echo
echo "Резултат: $pass успешни, $fail неуспешни."
[ "$fail" -eq 0 ] || exit 1
