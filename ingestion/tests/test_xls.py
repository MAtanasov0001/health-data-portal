"""Тестове за четеца на стар ``.xls`` (OLE2/BIFF8) — само стандартна библиотека."""

from __future__ import annotations

import struct
from pathlib import Path

from ingestion import xls

from ._xls_writer import write_xls


def test_reads_sheets_strings_and_numbers(tmp_path: Path) -> None:
    p = tmp_path / "book.xls"
    write_xls(
        p.as_posix(),
        [
            ("Lookup", [["код", "име"], ["A", "Алфа"]]),
            ("Данни", [["РЦЗ", "Брой"], ["0103211015", "Кирилица"], ["01", 42]]),
        ],
    )
    assert xls.sheet_names(p) == ["Lookup", "Данни"]
    assert list(xls.iter_rows(p, sheet=0)) == [["код", "име"], ["A", "Алфа"]]
    # Числата се връщат като низове по позиция; целите — без десетична част.
    assert list(xls.iter_rows(p, sheet=1)) == [
        ["РЦЗ", "Брой"],
        ["0103211015", "Кирилица"],
        ["01", "42"],
    ]


def _rk_int(n: int, div100: bool = False) -> int:
    rk = (n << 2) | 2
    return rk | 1 if div100 else rk


def _rk_float(x: float, div100: bool = False) -> int:
    bits = struct.unpack("<Q", struct.pack("<d", x))[0]
    rk = (bits >> 32) & 0xFFFFFFFC
    return rk | 1 if div100 else rk


def test_rk_number_decoding() -> None:
    assert xls._rk_to_number(_rk_int(7)) == 7.0
    assert xls._rk_to_number(_rk_int(500, div100=True)) == 5.0
    assert xls._rk_to_number(_rk_float(1.5)) == 1.5
    assert xls._rk_to_number(_rk_float(150.0, div100=True)) == 1.5


def test_sst_string_split_across_continue() -> None:
    # Един низ, разцепен на границата SST/CONTINUE: продължението носи нов grbit байт.
    head = struct.pack("<II", 1, 1) + struct.pack("<HB", 10, 0x00) + b"ABCD"
    cont = struct.pack("<B", 0x00) + b"EFGHIJ"
    strings = xls._parse_sst([(0x00FC, head), (0x003C, cont)])
    assert strings == ["ABCDEFGHIJ"]


def test_sst_multiple_unicode_strings() -> None:
    payload = struct.pack("<II", 2, 2)
    for s in ("Алфа", "Бета"):
        payload += struct.pack("<HB", len(s), 0x01) + s.encode("utf-16-le")
    assert xls._parse_sst([(0x00FC, payload)]) == ["Алфа", "Бета"]
