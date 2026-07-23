"""Сериализатори на дистрибуции — само стандартна библиотека (без външни зависимости).

Изпълнява МЕ34 (експорт в няколко формата): към наличните CSV/JSON тук се добавят
XLSX и RDF/Turtle. Всичко се произвежда с ``zipfile``/``xml`` и ръчна сериализация, за да
остане одитируемо и портируемо (същият принцип като четците в ``ingestion``).
"""

from __future__ import annotations

import datetime as _dt
import io
import itertools
import re
import zipfile
from collections.abc import Iterable
from typing import Any

# --- XLSX (минимален, поточен writer) -------------------------------------------------

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


def _chain(header: list[str], rows: Iterable[list[str]]) -> Iterable[list[str]]:
    return itertools.chain([header], rows)


def _col_ref(index: int) -> str:
    """0-базиран индекс на колона → буквен адрес (0→A, 26→AA)."""
    ref = ""
    n = index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        ref = chr(65 + rem) + ref
    return ref


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _cell_xml(col: int, row: int, value: str) -> str:
    if value == "":
        return ""
    ref = f"{_col_ref(col)}{row}"
    if _NUMERIC.match(value):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return (
        f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_xml_escape(value)}</t></is></c>'
    )


_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'  # noqa: E501
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'  # noqa: E501
    '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'  # noqa: E501
    "</Types>"
)

_ROOT_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'  # noqa: E501
    "</Relationships>"
)

_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="data" sheetId="1" r:id="rId1"/></sheets>'
    "</workbook>"
)

_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'  # noqa: E501
    "</Relationships>"
)

_SHEET_HEAD = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    "<sheetData>"
)
_SHEET_TAIL = "</sheetData></worksheet>"


def xlsx_bytes(header: list[str], rows: Iterable[list[str]]) -> bytes:
    """Сглобява минимален валиден .xlsx (един лист) поточно — хедър + редове.

    Числовите стойности се записват като числа, останалите като inline низове. Компресира се
    (ZIP_DEFLATED), така че големите набори остават практични за пренос.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _ROOT_RELS)
        zf.writestr("xl/workbook.xml", _WORKBOOK)
        zf.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        info = zipfile.ZipInfo("xl/worksheets/sheet1.xml")
        info.compress_type = zipfile.ZIP_DEFLATED
        with zf.open(info, "w") as sheet:
            sheet.write(_SHEET_HEAD.encode("utf-8"))
            row_no = 0
            for values in _chain(header, rows):
                row_no += 1
                cells = "".join(_cell_xml(c, row_no, v) for c, v in enumerate(values))
                sheet.write(f'<row r="{row_no}">{cells}</row>'.encode())
            sheet.write(_SHEET_TAIL.encode("utf-8"))
    return buf.getvalue()


# --- RDF / Turtle сериализация на DCAT-AP JSON-LD -------------------------------------

_PREFIXES: dict[str, str] = {
    "dcat": "http://www.w3.org/ns/dcat#",
    "dct": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "vcard": "http://www.w3.org/2006/vcard/ns#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "spdx": "http://spdx.org/rdf/terms#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "stat": "http://data.europa.eu/s1n/",
    "healthPortal": "https://data.health.egov.bg/def/",
}


def _ttl_literal(value: str, *, lang: str | None = None, dtype: str | None = None) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    out = f'"{escaped}"'
    if lang:
        return out + f"@{lang}"
    if dtype:
        return out + f"^^{dtype}"
    return out


def _ttl_term(value: Any) -> str:
    """Сериализира една JSON-LD стойност като Turtle терм (IRI, литерал или празен възел)."""
    if isinstance(value, dict):
        if "@value" in value:
            return _ttl_literal(
                str(value["@value"]),
                lang=value.get("@language"),
                dtype=value.get("@type"),
            )
        keys = set(value.keys())
        if keys == {"@id"}:
            return _ttl_iri(str(value["@id"]))
        return _ttl_blank(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return _ttl_literal(str(value))


def _ttl_iri(iri: str) -> str:
    return f"<{iri}>"


def _ttl_blank(node: dict[str, Any]) -> str:
    parts: list[str] = []
    if "@type" in node:
        parts.append(f"a {node['@type']}")
    for pred, val in node.items():
        if pred in ("@id", "@type"):
            continue
        parts.append(f"{pred} {_ttl_objects(val)}")
    return "[ " + " ; ".join(parts) + " ]"


def _ttl_objects(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(_ttl_term(v) for v in value)
    return _ttl_term(value)


def _dataset_triples(dcat: dict[str, Any]) -> str:
    subject = _ttl_iri(str(dcat["@id"]))
    lines = [f"{subject}"]
    preds: list[str] = []
    if "@type" in dcat:
        preds.append(f"    a {dcat['@type']}")
    for pred, val in dcat.items():
        if pred in ("@id", "@type"):
            continue
        preds.append(f"    {pred} {_ttl_objects(val)}")
    return "\n".join(lines) + "\n" + " ;\n".join(preds) + " .\n"


def _prefix_header() -> str:
    return "".join(f"@prefix {p}: <{ns}> .\n" for p, ns in _PREFIXES.items()) + "\n"


def dataset_to_turtle(dcat: dict[str, Any]) -> str:
    """DCAT-AP dcat:Dataset (JSON-LD dict) → Turtle документ."""
    return _prefix_header() + _dataset_triples(dcat)


def catalog_to_turtle(
    datasets: list[dict[str, Any]], *, base: str, title_bg: str, title_en: str, publisher: str
) -> str:
    """Каталог + вложените набори → Turtle документ."""
    now = _dt.datetime.now(_dt.UTC).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    now = now[:-2] + ":" + now[-2:]
    cat_iri = _ttl_iri(f"{base}/catalog")
    members = ", ".join(_ttl_iri(str(d["@id"])) for d in datasets) or ""
    body = [
        _prefix_header().rstrip("\n"),
        "",
        f"{cat_iri}",
        "    a dcat:Catalog ;",
        f"    dct:title {_ttl_literal(title_bg, lang='bg')}, {_ttl_literal(title_en, lang='en')} ;",
        f"    dct:publisher [ a foaf:Agent ; foaf:name {_ttl_literal(publisher)} ] ;",
        f"    dct:modified {_ttl_literal(now, dtype='xsd:dateTime')}"
        + (f" ;\n    dcat:dataset {members} ." if members else " ."),
        "",
    ]
    triples = "\n".join(_dataset_triples(d) for d in datasets)
    return "\n".join(body) + "\n" + triples
