"""Тестове за зареждащия адаптер НЗОК Activities (месечни .xlsx → годишен source.csv)."""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from ingestion.loaders import nhif_activities as loader

_SHEET_HEADER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
)


def _cell(ref: str, value: str) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def _write_xlsx(path: Path, rows: list[list[str]]) -> None:
    """Записва минимален .xlsx (inline низове) с даден списък от редове."""
    cols = "ABCDEFG"
    body = []
    for ri, row in enumerate(rows, start=1):
        cells = "".join(_cell(f"{cols[ci]}{ri}", v) for ci, v in enumerate(row))
        body.append(f'<row r="{ri}">{cells}</row>')
    sheet = _SHEET_HEADER + "".join(body) + "</sheetData></worksheet>"
    workbook = (
        '<?xml version="1.0"?><workbook '
        'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="s" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    ctypes = (
        '<?xml version="1.0"?><Types '
        'xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ctypes)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)


_HDR = [
    "РЗОК",
    "Име ЛЗБП",
    "КП/AПр/КПр",
    "Основна диагноза",
    "Вторична диагноза",
    "Брой случаи",
    "Брой ЗОЛ",
]
_TITLE = ["Отчетени брой случаи", "", "", "", "", "", ""]


def test_rzok_normalized_and_months_summed(tmp_path: Path) -> None:
    # Два месеца със СЪЩАТА клетка, но различен формат на РЗОК („код+име" срещу само код).
    _write_xlsx(
        tmp_path / "m01.xlsx",
        [_TITLE, _HDR, ["01 Благоевград", "МБАЛ X", "A19", "H25.1", "E11.9", "3", "2"]],
    )
    _write_xlsx(
        tmp_path / "m02.xlsx",
        [_TITLE, _HDR, ["01", "МБАЛ X", "A19", "H25.1", "E11.9", "4", "3"]],
    )
    agg = loader.aggregate(tmp_path)
    # Един ключ (регионът не се раздвоява), сумите се събират: случаи 3+4, ЗОЛ 2+3.
    assert len(agg) == 1
    key = ("01 Благоевград", "МБАЛ X", "A19", "H25.1", "E11.9")
    assert agg[key] == [5, 7]  # [ЗОЛ, случаи]

    out = tmp_path / "source.csv"
    loader.write_source_csv(agg, out)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows[0]["rzok"] == "01 Благоевград"
    assert rows[0]["broy_zol"] == "5"
    assert rows[0]["broy_sluchai"] == "7"


def test_missing_header_raises(tmp_path: Path) -> None:
    _write_xlsx(tmp_path / "bad.xlsx", [_TITLE, ["друго", "", "", "", "", "", ""]])
    try:
        loader.aggregate(tmp_path)
    except ValueError as exc:
        assert "хедър" in str(exc)
    else:
        raise AssertionError("очаква се ValueError при липсващ хедър")
