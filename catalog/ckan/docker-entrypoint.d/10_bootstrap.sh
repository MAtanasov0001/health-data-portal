#!/bin/bash
# Първоначална подготовка на CKAN за локална/демо среда (режим B).
#
# Идемпотентно: безопасно е да се стартира при всяко вдигане на контейнера.
#   1) инициализира схемата на базата (db init);
#   2) създава sysadmin потребител, ако липсва;
#   3) издава API токен за адаптера (catalog-sync) в споделен обем.
#
# ТАЙНИТЕ ТУК СА ЛОКАЛНИ ЗАМЕСТИТЕЛИ (виж infra/.env.example) — никога реални.
# Продукционните тайни се управляват от хранилище за тайни (режим C).
set -euo pipefail

CKAN_INI="${CKAN_INI:-/srv/app/ckan.ini}"
CKAN="/usr/lib/ckan/venv/bin/ckan -c ${CKAN_INI}"

echo "[bootstrap] инициализация на схемата на базата"
$CKAN db init || true

ADMIN_USER="${CKAN_SYSADMIN_NAME:-ckan_admin}"
ADMIN_PASS="${CKAN_SYSADMIN_PASSWORD:-change-me-local-only}"
ADMIN_MAIL="${CKAN_SYSADMIN_EMAIL:-admin@localhost}"

if ! $CKAN user show "$ADMIN_USER" >/dev/null 2>&1; then
  echo "[bootstrap] създаване на sysadmin '$ADMIN_USER'"
  $CKAN user add "$ADMIN_USER" \
      email="$ADMIN_MAIL" password="$ADMIN_PASS" || true
  $CKAN sysadmin add "$ADMIN_USER" || true
fi

# API токен за адаптера. Записва се в споделен обем, откъдето catalog-sync го чете.
SHARED_DIR="${CKAN_SHARED_DIR:-/shared}"
TOKEN_FILE="${SHARED_DIR}/ckan_api_token"
mkdir -p "$SHARED_DIR"
if [ ! -s "$TOKEN_FILE" ]; then
  echo "[bootstrap] издаване на API токен → $TOKEN_FILE"
  $CKAN user token add "$ADMIN_USER" sync \
      | tail -n1 | tr -d '[:space:]' > "$TOKEN_FILE" || true
fi

echo "[bootstrap] готово"
