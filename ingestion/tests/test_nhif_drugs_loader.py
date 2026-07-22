"""Тестове за зареждащия адаптер НЗОК болнични лекарства (месечни .xls → годишен source.csv)."""

from __future__ import annotations

import csv
from pathlib import Path

from ingestion.loaders import nhif_hospital_drugs as loader

from ._xls_writer import write_xls

_HDR: list[object] = [
    "РЦЗ",
    "Наименование на леч.заведение",
    "ATC код",
    "Международно непатентно наименование (INN)",
    "Национален №",
    "НЗОК код",
    "Търговско наименование",
    "Лекарствена форма",
    "Колич. на лекарственото в-во",
    "Брой в опаковка",
    "МКБ код",
    "Наименование на заболяването",
    "Брой на ЗОЛ-броени за периода",
    "Опаковки",
    "Реимбурсна сума",
]
_TITLE: list[object] = ["РАЗХОДИ И БРОЙ БОЛНИ ...", *([""] * 14)]


def _row(zol: object, opak: object, reimb: object) -> list[object]:
    return [
        "0103211015",
        "МБАЛ Пулс АД",
        "B03XA02",
        "DARBEPOETIN ALFA",
        "3461",
        "BH058",
        "Aranesp",
        "SOL",
        "150 mcg",
        "1",
        "C18.2",
        "Колон",
        zol,
        opak,
        reimb,
    ]


def test_region_derived_and_months_summed(tmp_path: Path) -> None:
    write_xls(
        (tmp_path / "drg-2025-01.xls").as_posix(),
        [("01.2025", [_TITLE, _HDR, _row(3, 2.0, 661.14)])],
    )
    write_xls(
        (tmp_path / "drg-2025-02.xls").as_posix(),
        [("02.2025", [_TITLE, _HDR, _row(5, 1.0, 330.5)])],
    )

    agg = loader.aggregate(tmp_path)
    assert len(agg) == 1
    key = next(iter(agg))
    assert key[0] == "01 Благоевград"  # регионът е изведен от първите две цифри на РЦЗ
    assert key[1] == "0103211015"
    zol, opak, reimb = agg[key]
    assert zol == 8  # 3 + 5
    assert round(opak, 3) == 3.0  # 2.0 + 1.0
    assert round(reimb, 2) == 991.64  # 661.14 + 330.5

    out = tmp_path / "source.csv"
    loader.write_source_csv(agg, out)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows[0]["rzok"] == "01 Благоевград"
    assert rows[0]["broy_zol"] == "8"
    assert rows[0]["reimbursna_suma"] == "991.64"


def test_missing_header_raises(tmp_path: Path) -> None:
    write_xls((tmp_path / "bad.xls").as_posix(), [("s", [["друго", "", ""]])])
    try:
        loader.aggregate(tmp_path)
    except ValueError as exc:
        assert "хедър" in str(exc)
    else:
        raise AssertionError("очаква се ValueError при липсващ хедър")
