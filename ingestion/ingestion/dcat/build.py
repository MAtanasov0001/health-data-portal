"""Изгражда DCAT-AP запис (JSON-LD) за набор от неговите метаданни и снапшот."""

from __future__ import annotations

from typing import Any

from ..disclosure import DisclosureReport
from ..models import DatasetMetadata
from ..snapshot import Snapshot

BASE = "https://data.health.egov.bg"
THEME_BASE = "http://publications.europa.eu/resource/authority/data-theme/"
FREQ_BASE = "http://publications.europa.eu/resource/authority/frequency/"
ACCESS_BASE = "http://publications.europa.eu/resource/authority/access-right/"
NUTS_BASE = "http://data.europa.eu/nuts/code/"
LICENSE_URI = {"CC-BY-4.0": "http://creativecommons.org/licenses/by/4.0/"}


def _lang_list(values: dict[str, str]) -> list[dict[str, str]]:
    return [{"@value": v, "@language": lang} for lang, v in values.items()]


def build_dataset(
    metadata: DatasetMetadata, snapshot: Snapshot, disclosure: DisclosureReport
) -> dict[str, Any]:
    """Връща DCAT-AP dcat:Dataset като JSON-LD dict."""
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
        "dcat:distribution": [
            {
                "@type": "dcat:Distribution",
                "@id": f"{ds_uri}/csv",
                "dcat:accessURL": {"@id": f"{ds_uri}/csv"},
                "dcat:downloadURL": {"@id": f"{BASE}/api/v1/datasets/{metadata.identifier}/data.csv"},
                "dct:format": {
                    "@id": "http://publications.europa.eu/resource/authority/file-type/CSV"
                },
                "spdx:checksum": {
                    "@type": "spdx:Checksum",
                    "spdx:algorithm": {
                        "@id": "http://spdx.org/rdf/terms#checksumAlgorithm_sha256"
                    },
                    "spdx:checksumValue": snapshot.checksum_sha256,
                },
                "dct:issued": {"@value": snapshot.created_at, "@type": "xsd:dateTime"},
            }
        ],
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
    return record
