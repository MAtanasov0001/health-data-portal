"""Минимален четец на .xlsx — само стандартна библиотека (без външни зависимости).

.xlsx е ZIP архив с XML части (OOXML/SpreadsheetML). Четем споделените низове
(``sharedStrings.xml``) и потока от редове на листа, без да зареждаме целия файл в паметта.
Достатъчен за държавни експорти-таблици (плосък лист с хедър + редове).

Ограничения (умишлени, за да остане тесен и одитируем): чете първия лист, връща стойностите
на клетките като низове по позиция; не интерпретира формати, формули или дати като типове.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    out: list[str] = []
    with zf.open("xl/sharedStrings.xml") as fh:
        for _, el in ET.iterparse(fh):
            if el.tag == _NS + "si":
                out.append("".join(t.text or "" for t in el.iter(_NS + "t")))
                el.clear()
    return out


def _first_sheet_path(zf: zipfile.ZipFile) -> str:
    names = zf.namelist()
    for candidate in ("xl/worksheets/sheet1.xml",):
        if candidate in names:
            return candidate
    sheets = sorted(n for n in names if n.startswith("xl/worksheets/") and n.endswith(".xml"))
    if not sheets:
        raise ValueError("Във файла няма работен лист (xl/worksheets/*.xml)")
    return sheets[0]


def _cell_value(cell: ET.Element, shared: list[str]) -> str:
    ctype = cell.get("t")
    if ctype == "inlineStr":
        node = cell.find(_NS + "is")
        return "".join(t.text or "" for t in node.iter(_NS + "t")) if node is not None else ""
    value = cell.find(_NS + "v")
    if value is None or value.text is None:
        return ""
    if ctype == "s":
        return shared[int(value.text)]
    return value.text


def iter_rows(path: str | Path) -> Iterator[list[str]]:
    """Итерира редовете на първия лист като списъци от низови стойности (по позиция)."""
    with zipfile.ZipFile(path) as zf:
        shared = _shared_strings(zf)
        sheet = _first_sheet_path(zf)
        with zf.open(sheet) as fh:
            for _, el in ET.iterparse(fh):
                if el.tag == _NS + "row":
                    yield [_cell_value(c, shared) for c in el.findall(_NS + "c")]
                    el.clear()
