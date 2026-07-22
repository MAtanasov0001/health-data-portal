"""Адаптер снапшот → CKAN.

Публикува неизменяемите снапшоти от приемната тръба като набори (packages) в CKAN,
който е каталожното ядро (вариант А). CKAN държи метаданните и осигурява DCAT-AP /
CKAN-съвместими крайни точки за харвестване; данните се поднасят от нашето API.

Свойства:
- **Идемпотентен** — сравнява по име (identifier); създава или обновява. Безопасен за
  повторно пускане (напр. след нов снапшот).
- **Само стандартна библиотека** — без външни зависимости (както и четящото API).
- **Режим B** — само метаданни. Токенът е локален (виж infra/.env.example).

Конфигурация (env):
    OHDP_SNAPSHOTS      корен на снапшотите            (по подр. /snapshots)
    CKAN_URL            базов адрес на CKAN            (по подр. http://ckan:5000)
    CKAN_API_TOKEN      токен; или CKAN_API_TOKEN_FILE (по подр. /shared/ckan_api_token)
    OHDP_API_BASE       публичен адрес на данните      (по подр. http://localhost:8000)
    CKAN_ORG            организация-собственик         (по подр. midt)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

NUTS_BASE = "http://data.europa.eu/nuts/code/"


class CkanError(RuntimeError):
    """CKAN Action API върна неуспех."""


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _token() -> str:
    tok = os.environ.get("CKAN_API_TOKEN", "").strip()
    if tok:
        return tok
    path = Path(_env("CKAN_API_TOKEN_FILE", "/shared/ckan_api_token"))
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    raise CkanError("Липсва CKAN API токен (CKAN_API_TOKEN или CKAN_API_TOKEN_FILE).")


def _call(base: str, token: str, action: str, payload: dict[str, Any]) -> Any:
    """Извиква CKAN Action API. Връща 'result' или вдига CkanError."""
    url = f"{base.rstrip('/')}/api/3/action/{action}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise CkanError(f"{action}: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise CkanError(f"{action}: няма връзка с CKAN ({exc.reason})") from exc
    if not body.get("success"):
        raise CkanError(f"{action}: {body.get('error')}")
    return body.get("result")


def _exists(base: str, token: str, action: str, obj_id: str) -> Any | None:
    try:
        return _call(base, token, action, {"id": obj_id})
    except CkanError:
        return None


def _titles(dcat: dict[str, Any]) -> dict[str, str]:
    return {
        t["@language"]: t["@value"]
        for t in dcat.get("dct:title", [])
        if "@language" in t
    }


def _descriptions(dcat: dict[str, Any]) -> dict[str, str]:
    return {
        d["@language"]: d["@value"]
        for d in dcat.get("dct:description", [])
        if "@language" in d
    }


def _tags(dcat: dict[str, Any]) -> list[dict[str, str]]:
    seen: set[str] = set()
    tags: list[dict[str, str]] = []
    for kw in dcat.get("dcat:keyword", []):
        name = str(kw.get("@value", "")).strip()
        if 2 <= len(name) <= 100 and name not in seen:
            seen.add(name)
            tags.append({"name": name})
    return tags


def _themes(dcat: dict[str, Any]) -> list[str]:
    return [t["@id"] for t in dcat.get("dcat:theme", []) if "@id" in t]


def _first(values: dict[str, str]) -> str:
    return values.get("bg") or next(iter(values.values()), "")


def _package(
    manifest: dict[str, Any],
    dcat: dict[str, Any],
    *,
    org: str,
    api_base: str,
) -> dict[str, Any]:
    """Съставя CKAN package dict от снапшот, съвместим с ckanext-dcat."""
    ident = manifest["identifier"]
    titles = _titles(dcat)
    descriptions = _descriptions(dcat)
    disclosure = dcat.get("healthPortal:disclosureControl", {})
    spatial = [s["@id"].rsplit("/", 1)[-1] for s in dcat.get("dct:spatial", [])]
    temporal = dcat.get("dct:temporal", {})

    extras: list[dict[str, str]] = [
        {"key": "identifier", "value": ident},
        {"key": "issued", "value": manifest["created_at"]},
        {"key": "modified", "value": manifest["created_at"]},
        {"key": "theme", "value": json.dumps(_themes(dcat))},
        {"key": "checksum_sha256", "value": manifest["checksum_sha256"]},
        {"key": "disclosure_method", "value": str(disclosure.get("method", ""))},
        {
            "key": "disclosure_min_cell_size",
            "value": str(disclosure.get("minCellSize", "")),
        },
    ]
    if spatial:
        extras.append({"key": "spatial_uri", "value": NUTS_BASE + spatial[0]})
    if isinstance(temporal, dict) and temporal.get("dcat:startDate"):
        extras.append({"key": "temporal_start", "value": temporal["dcat:startDate"]})
    if isinstance(temporal, dict) and temporal.get("dcat:endDate"):
        extras.append({"key": "temporal_end", "value": temporal["dcat:endDate"]})

    license_raw = dcat.get("dct:license", {}).get("@id", "")
    license_id = "cc-by" if "creativecommons.org/licenses/by/4.0" in license_raw else ""

    data_url = f"{api_base.rstrip('/')}/v1/datasets/{ident}"
    resources = [
        {
            "name": "CSV",
            "format": "CSV",
            "mimetype": "text/csv",
            "url": f"{data_url}/data.csv",
        },
        {
            "name": "JSON",
            "format": "JSON",
            "mimetype": "application/json",
            "url": f"{data_url}/data.json",
        },
    ]

    return {
        "name": ident,
        "title": _first(titles),
        "notes": _first(descriptions),
        "version": manifest["version"],
        "owner_org": org,
        "license_id": license_id,
        "tags": _tags(dcat),
        "extras": extras,
        "resources": resources,
    }


def _ensure_org(base: str, token: str, org: str) -> None:
    if _exists(base, token, "organization_show", org) is None:
        _call(
            base,
            token,
            "organization_create",
            {"name": org, "title": "МИДТ — Портал за отворени здравни данни"},
        )
        print(f"[sync] създадена организация '{org}'")


def _upsert(base: str, token: str, pkg: dict[str, Any]) -> str:
    existing = _exists(base, token, "package_show", pkg["name"])
    if existing is None:
        _call(base, token, "package_create", pkg)
        return "създаден"
    pkg["id"] = existing["id"]
    _call(base, token, "package_update", pkg)
    return "обновен"


def _latest_snapshots(root: Path) -> list[Path]:
    """Връща пътя до най-новата версия на всеки набор (по семантична версия)."""
    out: list[Path] = []
    if not root.is_dir():
        return out
    for ds_dir in sorted(root.iterdir()):
        if not ds_dir.is_dir():
            continue
        versions = [v for v in ds_dir.iterdir() if (v / "manifest.json").is_file()]
        if not versions:
            continue
        latest = max(versions, key=lambda v: _semver(v.name))
        out.append(latest)
    return out


def _semver(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in version.split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return tuple(parts)


def main() -> int:
    base = _env("CKAN_URL", "http://ckan:5000")
    api_base = _env("OHDP_API_BASE", "http://localhost:8000")
    org = _env("CKAN_ORG", "midt")
    root = Path(_env("OHDP_SNAPSHOTS", "/snapshots"))

    try:
        token = _token()
        _ensure_org(base, token, org)
        snapshots = _latest_snapshots(root)
        if not snapshots:
            print(f"[sync] няма снапшоти в {root} — нищо за публикуване")
            return 0
        for snap in snapshots:
            manifest = json.loads((snap / "manifest.json").read_text("utf-8"))
            dcat = json.loads((snap / "dcat.jsonld").read_text("utf-8"))
            pkg = _package(manifest, dcat, org=org, api_base=api_base)
            status = _upsert(base, token, pkg)
            print(f"[sync] {pkg['name']}@{pkg['version']} — {status}")
    except CkanError as exc:
        print(f"[sync] ГРЕШКА: {exc}", file=sys.stderr)
        return 1
    print("[sync] готово")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
