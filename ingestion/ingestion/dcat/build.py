"""Изгражда DCAT-AP запис (JSON-LD) за набор от неговите метаданни и снапшот."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from ..disclosure import DisclosureReport
from ..models import DatasetMetadata, DisclosureSpec
from ..snapshot import Snapshot

# Каноничният домейн на портала. Конфигурируем чрез ``OHDP_BASE_URL`` (същата променлива като в
# публичното API), за да не е зашит хостът в снапшотите — DCAT @id/URL следват средата (чл. 16:
# без обвързване с доставчик/домейн). По подразбиране — продукционният домейн на портала.
BASE = os.environ.get("OHDP_BASE_URL", "https://data.health.egov.bg").rstrip("/")
THEME_BASE = "http://publications.europa.eu/resource/authority/data-theme/"
FREQ_BASE = "http://publications.europa.eu/resource/authority/frequency/"
ACCESS_BASE = "http://publications.europa.eu/resource/authority/access-right/"
FILE_TYPE_BASE = "http://publications.europa.eu/resource/authority/file-type/"
NUTS_BASE = "http://data.europa.eu/nuts/code/"
LICENSE_URI = {"CC-BY-4.0": "http://creativecommons.org/licenses/by/4.0/"}

# Дистрибуции по МЕ34 (експорт в няколко формата). CSV носи контролната сума на снапшота;
# останалите формати се произвеждат от API-то при поискване (същите данни, различен пренос).
_DISTRIBUTIONS = [
    ("data.csv", "CSV", "text/csv", True),
    ("data.json", "JSON", "application/json", False),
    (
        "data.xlsx",
        "XLSX",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        False,
    ),
    ("dcat.ttl", "RDF_TURTLE", "text/turtle", False),
]


def _lang_list(values: dict[str, str]) -> list[dict[str, str]]:
    return [{"@value": v, "@language": lang} for lang, v in values.items()]


def _distributions(identifier: str, snapshot: Snapshot) -> list[dict[str, Any]]:
    api = f"{BASE}/api/v1/datasets/{identifier}"
    ds_uri = f"{BASE}/dataset/{identifier}"
    out: list[dict[str, Any]] = []
    for path, ftype, media, with_checksum in _DISTRIBUTIONS:
        dist: dict[str, Any] = {
            "@type": "dcat:Distribution",
            "@id": f"{ds_uri}/{ftype.lower()}",
            "dcat:accessURL": {"@id": f"{api}/{path}"},
            "dcat:downloadURL": {"@id": f"{api}/{path}"},
            "dcat:mediaType": media,
            "dct:format": {"@id": FILE_TYPE_BASE + ftype},
            "dct:issued": {"@value": snapshot.created_at, "@type": "xsd:dateTime"},
        }
        if with_checksum:
            dist["spdx:checksum"] = {
                "@type": "spdx:Checksum",
                "spdx:algorithm": {"@id": "http://spdx.org/rdf/terms#checksumAlgorithm_sha256"},
                "spdx:checksumValue": snapshot.checksum_sha256,
            }
        out.append(dist)
    return out


def _concept(kind: str, column: str) -> dict[str, Any]:
    """Локален skos:Concept за измерение/атрибут по StatDCAT-AP (стабилен IRI + етикет)."""
    return {
        "@id": f"{BASE}/def/{kind}/{quote(column, safe='')}",
        "@type": "skos:Concept",
        "skos:prefLabel": {"@value": column, "@language": "bg"},
    }


def _statistical(spec: DisclosureSpec, snapshot: Snapshot) -> dict[str, Any]:
    """StatDCAT-AP свойства за статистически набор (измерения, атрибут-мярка, брой серии).

    Порталните набори са агрегатна статистика (измерения + мярка), затова се описват по
    StatDCAT-AP (namespace ``stat`` = http://data.europa.eu/s1n/): ``stat:dimension`` за
    измеренията, ``stat:attribute`` за мерната колона и ``stat:numSeries`` за броя серии.
    """
    return {
        "stat:numSeries": {
            "@value": str(snapshot.row_count),
            "@type": "xsd:nonNegativeInteger",
        },
        "stat:dimension": [_concept("dimension", d) for d in spec.dimension_columns],
        "stat:attribute": [_concept("attribute", spec.measure_column)],
    }


def build_dataset(
    metadata: DatasetMetadata,
    snapshot: Snapshot,
    disclosure: DisclosureReport,
    *,
    stat_spec: DisclosureSpec | None = None,
) -> dict[str, Any]:
    """Връща DCAT-AP dcat:Dataset като JSON-LD dict.

    Ако е подадена ``stat_spec`` (структурата за контрол на разкриването), наборът се обогатява
    със StatDCAT-AP свойства — той е агрегатна статистика с измерения и мярка.
    """
    ds_uri = f"{BASE}/dataset/{metadata.identifier}"
    record: dict[str, Any] = {
        "@id": ds_uri,
        "@type": "dcat:Dataset",
        "dct:identifier": metadata.identifier,
        "dct:title": _lang_list(metadata.title),
        "dct:description": _lang_list(metadata.description),
        "dct:publisher": {"@type": "foaf:Agent", "foaf:name": metadata.publisher},
        "dcat:contactPoint": {
            "@type": "vcard:Organization",
            "vcard:hasEmail": f"mailto:{metadata.contact_email}",
        },
        "dcat:theme": [{"@id": THEME_BASE + t} for t in metadata.theme],
        "owl:versionInfo": snapshot.version,
        "dct:issued": {"@value": snapshot.created_at, "@type": "xsd:dateTime"},
        "dct:modified": {"@value": snapshot.created_at, "@type": "xsd:dateTime"},
        "dct:accessRights": {"@id": ACCESS_BASE + metadata.access_rights},
        "healthPortal:disclosureControl": {
            "method": "small-cell-suppression",
            "minCellSize": disclosure.min_cell_size,
            "appliedAt": snapshot.created_at,
        },
        "dcat:distribution": _distributions(metadata.identifier, snapshot),
    }
    if metadata.spatial:
        record["dct:spatial"] = [{"@id": NUTS_BASE + s} for s in metadata.spatial]
    if metadata.accrual_periodicity:
        record["dct:accrualPeriodicity"] = {"@id": FREQ_BASE + metadata.accrual_periodicity}
    if metadata.license in LICENSE_URI:
        record["dct:license"] = {"@id": LICENSE_URI[metadata.license]}
    if metadata.keyword:
        record["dcat:keyword"] = [
            {"@value": kw, "@language": lang}
            for lang, kws in metadata.keyword.items()
            for kw in kws
        ]
    if stat_spec is not None:
        record.update(_statistical(stat_spec, snapshot))
    return record
