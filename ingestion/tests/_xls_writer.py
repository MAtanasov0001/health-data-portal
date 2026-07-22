"""Минимален OLE2 + BIFF8 писач за тестове (огледало на ``xls.py`` четеца).

Строи истински ``.xls`` (OLE2 съставен файл с поток ``Workbook``) с даден списък листове,
за да се тества четецът end-to-end без реални (gitignore-нати) файлове. Достатъчен за теста:
низови клетки (SST + LABELSST) и числа (NUMBER). Не покрива RK/MULRK — те се тестват отделно.
"""

from __future__ import annotations

import struct

_ENDOFCHAIN = 0xFFFFFFFE
_FREESECT = 0xFFFFFFFF
_FATSECT = 0xFFFFFFFD


def _rec(rt: int, payload: bytes) -> bytes:
    return struct.pack("<HH", rt, len(payload)) + payload


def _bof(dt: int) -> bytes:
    return _rec(0x0809, struct.pack("<HH", 0x0600, dt) + b"\x00" * 12)


def _eof() -> bytes:
    return _rec(0x000A, b"")


def _sst(strings: list[str]) -> bytes:
    payload = struct.pack("<II", len(strings), len(strings))
    for s in strings:
        payload += struct.pack("<HB", len(s), 0x01) + s.encode("utf-16-le")
    return _rec(0x00FC, payload)


def _boundsheet(name: str) -> bytes:
    nb = name.encode("utf-16-le")
    return _rec(0x0085, struct.pack("<IHBB", 0, 0, len(name), 0x01) + nb)


def _labelsst(r: int, c: int, isst: int) -> bytes:
    return _rec(0x00FD, struct.pack("<HHHI", r, c, 0, isst))


def _number(r: int, c: int, value: float) -> bytes:
    return _rec(0x0203, struct.pack("<HHHd", r, c, 0, float(value)))


def _dir_entry(name: str, etype: int, start: int, size: int) -> bytes:
    nb = name.encode("utf-16-le") + b"\x00\x00"
    e = nb + b"\x00" * (64 - len(nb))
    e += struct.pack("<H", len(nb))  # name length incl. terminator
    e += bytes([etype, 0])  # object type, colour
    e += struct.pack("<III", _FREESECT, _FREESECT, _FREESECT)  # left/right/child sids
    e += b"\x00" * 16  # clsid
    e += struct.pack("<I", 0)  # state bits
    e += b"\x00" * 16  # created/modified times
    e += struct.pack("<I", start)
    e += struct.pack("<I", size)
    e += b"\x00" * 4  # size high / reserved
    return e


def _ole2(stream: bytes) -> bytes:
    ss = 512
    padded = stream + b"\x00" * (-len(stream) % ss)
    if len(padded) < 4096:  # stay above the mini-stream cutoff → big-FAT path
        padded += b"\x00" * (4096 - len(padded))
    k = len(padded) // ss
    dir_sect, fat_sect = k, k + 1

    fat = [_FREESECT] * 128
    for i in range(k - 1):
        fat[i] = i + 1
    fat[k - 1] = _ENDOFCHAIN
    fat[dir_sect] = _ENDOFCHAIN
    fat[fat_sect] = _FATSECT
    fat_bytes = struct.pack("<128I", *fat)

    directory = (
        _dir_entry("Root Entry", 5, _ENDOFCHAIN, 0)
        + _dir_entry("Workbook", 2, 0, len(padded))  # padded ≥ mini cutoff → big-FAT path
    )
    directory += b"\x00" * (ss - len(directory))

    header = bytearray(512)
    header[0:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    struct.pack_into("<H", header, 24, 0x003E)  # minor version
    struct.pack_into("<H", header, 26, 0x0003)  # major version (v3, 512B sectors)
    struct.pack_into("<H", header, 28, 0xFFFE)  # byte order
    struct.pack_into("<H", header, 30, 9)  # sector shift
    struct.pack_into("<H", header, 32, 6)  # mini sector shift
    struct.pack_into("<I", header, 44, 1)  # num FAT sectors
    struct.pack_into("<I", header, 48, dir_sect)  # first directory sector
    struct.pack_into("<I", header, 56, 4096)  # mini stream cutoff
    struct.pack_into("<I", header, 60, _ENDOFCHAIN)  # first mini-FAT sector
    struct.pack_into("<I", header, 68, _ENDOFCHAIN)  # first DIFAT sector
    for i in range(109):  # DIFAT array in the header
        struct.pack_into("<I", header, 76 + i * 4, fat_sect if i == 0 else _FREESECT)

    return bytes(header) + padded + directory + fat_bytes


def write_xls(path: str, sheets: list[tuple[str, list[list[object]]]]) -> None:
    """Записва .xls с дадените листове. Всеки лист е (име, редове); клетка = str или число."""
    strings: list[str] = []
    index: dict[str, int] = {}
    for _name, rows in sheets:
        for row in rows:
            for value in row:
                if isinstance(value, str) and value not in index:
                    index[value] = len(strings)
                    strings.append(value)

    stream = _bof(0x0005) + _sst(strings)
    for name, _rows in sheets:
        stream += _boundsheet(name)
    stream += _eof()
    for _name, rows in sheets:
        stream += _bof(0x0010)
        for ri, row in enumerate(rows):
            for ci, value in enumerate(row):
                if isinstance(value, str):
                    stream += _labelsst(ri, ci, index[value])
                else:
                    stream += _number(ri, ci, float(value))  # type: ignore[arg-type]
        stream += _eof()

    with open(path, "wb") as fh:
        fh.write(_ole2(stream))
