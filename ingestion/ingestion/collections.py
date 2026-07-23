"""Приемане на *колекции* — групи свързани таблици (Eurostat-подобен модел).

За разлика от основната тръба (``pipeline.py``), тук данните са **предварително агрегирани
публични броеве** (по област, по вид, по месец…). Затова:

- няма контрол на разкриването (няма запис-ниво идентификатори за защита);
- схемата се *извежда* от CSV-то — числовите колони стават мерки, останалите — измерения.

Всяка таблица се записва като самостоятелен неизменяем снапшот със същата подредба като
основната тръба (``data.csv`` + ``manifest.json`` + ``dcat.jsonld``), затова публичното API я
поднася без промени. Принадлежността към колекция се пази в манифеста (поле ``collection``),
а не в идентификатора — така API-то може да групира таблиците в дърво.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from .timeutil import now_iso

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_THEME_BASE = "http://publications.europa.eu/resource/authority/data-theme/"
_ACCESS_BASE = "http://publications.europa.eu/resource/authority/access-right/"
_FILE_TYPE_BASE = "http://publications.europa.eu/resource/authority/file-type/"
_LICENSE_URI = {"CC-BY-4.0": "http://creativecommons.org/licenses/by/4.0/"}


class TableSpec(BaseModel):
    """Една таблица от колекцията (описателни метаданни; схемата се извежда от CSV-то)."""

    file: str
    identifier: str
    title: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)

    @field_validator("identifier")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _SLUG.fullmatch(v):
            raise ValueError("identifier на таблица трябва да е slug (малки букви, цифри, тире)")
        return v


class CollectionSpec(BaseModel):
    """Съдържанието на ``collection.yaml`` — метаданни на групата + списък с таблици."""

    identifier: str
    title: dict[str, str]
    description: dict[str, str]
    publisher: str
    contact_email: str
    theme: list[str] = Field(default_factory=list)
    keyword: dict[str, list[str]] = Field(default_factory=dict)
    license: str = "CC-BY-4.0"
    version: str = "1.0.0"
    tables: list[TableSpec]

    @field_validator("identifier")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not _SLUG.fullmatch(v):
            raise ValueError("identifier на колекция трябва да е slug")
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> CollectionSpec:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)


@dataclass
class TableResult:
    identifier: str
    row_count: int
    dimensions: list[str]
    measures: list[str]
    path: Path


@dataclass
class CollectionResult:
    identifier: str
    version: str
    tables: list[TableResult] = field(default_factory=list)


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, [])
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    return header, rows


def _is_number(value: str) -> bool:
    v = value.strip().replace(" ", "")
    if v == "":
        return False
    try:
        float(v.replace(",", "."))
    except ValueError:
        return False
    return True


def infer_schema(header: list[str], rows: list[list[str]]) -> tuple[list[str], list[str]]:
    """Извежда (измерения, мерки): колона е *мярка*, ако всяка непразна стойност е число."""
    measures: list[str] = []
    dimensions: list[str] = []
    for i, name in enumerate(header):
        values = [row[i] for row in rows if i < len(row) and row[i].strip() != ""]
        if values and all(_is_number(v) for v in values):
            measures.append(name)
        else:
            dimensions.append(name)
    return dimensions, measures


def _lang_list(values: dict[str, str]) -> list[dict[str, str]]:
    return [{"@value": v, "@language": lang} for lang, v in values.items() if v]


def _build_dcat(
    *,
    spec: CollectionSpec,
    table: TableSpec,
    identifier: str,
    created_at: str,
    checksum: str,
    base: str,
) -> dict[str, Any]:
    """Минимален, но валиден DCAT-AP запис за таблица от колекция."""
    ds_uri = f"{base}/dataset/{identifier}"
    api = f"{base}/api/v1/datasets/{identifier}"
    title = {**spec.title, **table.title}
    description = table.description or spec.description
    record: dict[str, Any] = {
        "@id": ds_uri,
        "@type": "dcat:Dataset",
        "dct:identifier": identifier,
        "dct:title": _lang_list(title),
        "dct:description": _lang_list(description),
        "dct:publisher": {"@type": "foaf:Agent", "foaf:name": spec.publisher},
        "dcat:contactPoint": {
            "@type": "vcard:Organization",
            "vcard:hasEmail": f"mailto:{spec.contact_email}",
        },
        "dcat:theme": [{"@id": _THEME_BASE + t} for t in spec.theme],
        "owl:versionInfo": spec.version,
        "dct:issued": {"@value": created_at, "@type": "xsd:dateTime"},
        "dct:modified": {"@value": created_at, "@type": "xsd:dateTime"},
        "dct:accessRights": {"@id": _ACCESS_BASE + "PUBLIC"},
        "healthPortal:collection": {
            "id": spec.identifier,
            "title": _lang_list(spec.title),
        },
        "dcat:distribution": [
            {
                "@type": "dcat:Distribution",
                "@id": f"{ds_uri}/csv",
                "dcat:accessURL": {"@id": f"{ds_uri}/csv"},
                "dcat:downloadURL": {"@id": f"{api}/data.csv"},
                "dct:format": {"@id": _FILE_TYPE_BASE + "CSV"},
                "spdx:checksum": {
                    "@type": "spdx:Checksum",
                    "spdx:algorithm": {
                        "@id": "http://spdx.org/rdf/terms#checksumAlgorithm_sha256"
                    },
                    "spdx:checksumValue": checksum,
                },
                "dct:issued": {"@value": created_at, "@type": "xsd:dateTime"},
            }
        ],
    }
    if spec.license in _LICENSE_URI:
        record["dct:license"] = {"@id": _LICENSE_URI[spec.license]}
    return record


def _write_table(
    *, out_root: Path, spec: CollectionSpec, table: TableSpec, source_dir: Path, base: str
) -> TableResult:
    identifier = f"{spec.identifier}-{table.identifier}"
    target = out_root / identifier / spec.version
    if target.exists():
        raise FileExistsError(
            f"Снапшот {identifier}@{spec.version} вече съществува — версиите са неизменяеми "
            f"(чл. 14). Вдигни version в collection.yaml."
        )

    header, rows = _read_csv(source_dir / table.file)
    if not header:
        raise ValueError(f"Празен CSV: {table.file}")
    dimensions, measures = infer_schema(header, rows)
    if not measures:
        raise ValueError(f"Таблицата {table.file} няма нито една числова (мерна) колона")

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    csv_text = buf.getvalue()
    checksum = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
    created_at = now_iso()

    target.mkdir(parents=True, exist_ok=False)
    (target / "data.csv").write_text(csv_text, encoding="utf-8")

    manifest = {
        "identifier": identifier,
        "version": spec.version,
        "created_at": created_at,
        "checksum_sha256": checksum,
        "row_count": len(rows),
        "columns": header,
        "dimensions": dimensions,
        "measures": measures,
        "collection": {
            "id": spec.identifier,
            "title": spec.title,
            "description": spec.description,
            "table": table.identifier,
            "table_title": table.title,
        },
        "disclosure_control": {"method": "none", "reason": "pre-aggregated-public-counts"},
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    dcat = _build_dcat(
        spec=spec,
        table=table,
        identifier=identifier,
        created_at=created_at,
        checksum=checksum,
        base=base,
    )
    (target / "dcat.jsonld").write_text(
        json.dumps(dcat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return TableResult(
        identifier=identifier,
        row_count=len(rows),
        dimensions=dimensions,
        measures=measures,
        path=target,
    )


def run_collection(
    collection_dir: Path, out_root: Path, *, base: str | None = None
) -> CollectionResult:
    """Приема цяла колекция: за всяка таблица записва самостоятелен снапшот."""
    import os

    spec = CollectionSpec.from_yaml(collection_dir / "collection.yaml")
    resolved_base = (base or os.environ.get("OHDP_BASE_URL", "https://data.health.egov.bg")).rstrip(
        "/"
    )
    tables_dir = collection_dir / "tables"
    result = CollectionResult(identifier=spec.identifier, version=spec.version)
    for table in spec.tables:
        tr = _write_table(
            out_root=out_root,
            spec=spec,
            table=table,
            source_dir=tables_dir,
            base=resolved_base,
        )
        result.tables.append(tr)
    return result
