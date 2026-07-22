"""Минимален четец на стар ``.xls`` (BIFF8 в OLE2 съставен файл) — само стандартна библиотека.

Реалните експорти на НЗОК за болничните лекарства идват в **стария** двоичен формат ``.xls``
(OLE2/BIFF8), който ``xlsx.py`` (OOXML/ZIP) не разбира, а стандартната библиотека няма готов
четец. За да остане приемната тръба **без външни зависимости** (принцип на модула), тук е
тесен четец, покриващ точно това, което тези експорти ползват:

* OLE2 съставен файл: заглавие, DIFAT/FAT, директория, голям и мини поток → съдържимо на
  вградения поток ``Workbook``;
* BIFF8 записи: ``SST`` (споделени низове, вкл. продължения през ``CONTINUE`` и низове,
  разцепени на границата), ``LABELSST``/``LABEL`` (текст), ``RK``/``MULRK``/``NUMBER`` (числа).

Ограничения (умишлени, за да остане одитируем): не интерпретира формати/дати като типове;
връща стойностите като низове по позиция (както ``xlsx.iter_rows``). Не поддържа шифроване.
"""

from __future__ import annotations

import struct
from collections.abc import Iterator
from pathlib import Path

_ENDOFCHAIN = 0xFFFFFFFE
_FREESECT = 0xFFFFFFFF

# BIFF record types used here.
_BOF = 0x0809
_EOF = 0x000A
_SST = 0x00FC
_CONTINUE = 0x003C
_BOUNDSHEET = 0x0085
_LABELSST = 0x00FD
_LABEL = 0x0204
_RK = 0x027E
_MULRK = 0x00BD
_NUMBER = 0x0203
_SUBSTREAM_WORKSHEET = 0x0010


class _Ole2:
    """Достатъчно от OLE2 съставния файл, за да прочетем именуван поток (напр. ``Workbook``)."""

    def __init__(self, data: bytes) -> None:
        self._d = data
        (self._sect_shift,) = struct.unpack_from("<H", data, 30)
        (self._mini_shift,) = struct.unpack_from("<H", data, 32)
        (self._num_fat,) = struct.unpack_from("<I", data, 44)
        (self._dir_start,) = struct.unpack_from("<I", data, 48)
        (self._mini_cutoff,) = struct.unpack_from("<I", data, 56)
        (self._minifat_start,) = struct.unpack_from("<I", data, 60)
        (self._difat_start,) = struct.unpack_from("<I", data, 68)
        self._ss = 1 << self._sect_shift
        self._mss = 1 << self._mini_shift
        self._read_fat()
        self._read_dir()
        self._read_minifat()

    def _sect_off(self, s: int) -> int:
        return 512 + s * self._ss

    def _sector(self, s: int) -> bytes:
        return self._d[self._sect_off(s) : self._sect_off(s) + self._ss]

    def _read_fat(self) -> None:
        difat = list(struct.unpack_from("<109I", self._d, 76))
        s = self._difat_start
        per = self._ss // 4
        while s not in (_ENDOFCHAIN, _FREESECT):
            entries = struct.unpack_from(f"<{per}I", self._d, self._sect_off(s))
            difat.extend(entries[:-1])
            s = entries[-1]
        fat: list[int] = []
        for sec in [x for x in difat if x != _FREESECT][: self._num_fat]:
            fat.extend(struct.unpack_from(f"<{per}I", self._d, self._sect_off(sec)))
        self._fat = fat

    def _chain(self, start: int) -> list[int]:
        out: list[int] = []
        s = start
        while s not in (_ENDOFCHAIN, _FREESECT) and s < len(self._fat):
            out.append(s)
            s = self._fat[s]
        return out

    def _big_stream(self, start: int, size: int) -> bytes:
        return b"".join(self._sector(s) for s in self._chain(start))[:size]

    def _read_dir(self) -> None:
        raw = self._big_stream(self._dir_start, len(self._d))
        self._entries: dict[str, tuple[int, int, int]] = {}
        self._root_start = 0
        self._root_size = 0
        for i in range(len(raw) // 128):
            e = raw[i * 128 : (i + 1) * 128]
            (nlen,) = struct.unpack_from("<H", e, 64)
            if nlen == 0:
                continue
            name = e[: nlen - 2].decode("utf-16-le", "replace")
            etype = e[66]
            (start,) = struct.unpack_from("<I", e, 116)
            (size,) = struct.unpack_from("<I", e, 120)
            if etype == 5:  # root entry holds the mini-stream container
                self._root_start, self._root_size = start, size
            self._entries[name] = (etype, start, size)

    def _read_minifat(self) -> None:
        if self._minifat_start == _ENDOFCHAIN:
            self._minifat: list[int] = []
            self._mini_container = b""
            return
        raw = self._big_stream(self._minifat_start, len(self._d))
        self._minifat = list(struct.unpack_from(f"<{len(raw) // 4}I", raw))
        self._mini_container = (
            self._big_stream(self._root_start, self._root_size) if self._root_start else b""
        )

    def _mini_stream(self, start: int, size: int) -> bytes:
        out: list[bytes] = []
        s = start
        while s not in (_ENDOFCHAIN, _FREESECT) and s < len(self._minifat):
            out.append(self._mini_container[s * self._mss : (s + 1) * self._mss])
            s = self._minifat[s]
        return b"".join(out)[:size]

    def stream(self, name: str) -> bytes:
        _etype, start, size = self._entries[name]
        if size >= self._mini_cutoff:
            return self._big_stream(start, size)
        return self._mini_stream(start, size)


def _records(buf: bytes) -> list[tuple[int, bytes]]:
    out: list[tuple[int, bytes]] = []
    i, n = 0, len(buf)
    while i + 4 <= n:
        rt, rl = struct.unpack_from("<HH", buf, i)
        out.append((rt, buf[i + 4 : i + 4 + rl]))
        i += 4 + rl
    return out


def _parse_sst(records: list[tuple[int, bytes]]) -> list[str]:
    """Разчита споделените низове (``SST`` + ``CONTINUE``), вкл. низове, разцепени на границата.

    На всяка граница ``CONTINUE`` продължаващият низ носи нов байт ``grbit`` (значим е само
    битът ``fHighByte``), затова четенето на знаци следи сегментите ръчно.
    """
    segs = [data for rt, data in records if rt == _SST]
    conts: list[bytes] = []
    seen_sst = False
    for rt, data in records:
        if rt == _SST:
            seen_sst = True
        elif rt == _CONTINUE and seen_sst:
            conts.append(data)
        elif seen_sst and rt not in (_SST, _CONTINUE):
            break
    if not segs:
        return []
    seg_data = [segs[0], *conts]
    _total, unique = struct.unpack_from("<II", seg_data[0], 0)
    seg_idx, pos = 0, 8  # skip total/unique header in the first segment
    strings: list[str] = []
    for _ in range(unique):
        d = seg_data[seg_idx]
        while pos + 3 > len(d):  # header never splits across a boundary
            seg_idx += 1
            pos = 0
            d = seg_data[seg_idx]
        cch, grbit = struct.unpack_from("<HB", d, pos)
        pos += 3
        f_high = grbit & 0x01
        crun = 0
        cch_ext = 0
        if grbit & 0x08:  # rich text
            (crun,) = struct.unpack_from("<H", d, pos)
            pos += 2
        if grbit & 0x04:  # phonetic (Far East)
            (cch_ext,) = struct.unpack_from("<I", d, pos)
            pos += 4
        parts: list[str] = []
        remaining = cch
        while remaining > 0:
            d = seg_data[seg_idx]
            if pos >= len(d):
                seg_idx += 1
                pos = 0
                (newg,) = struct.unpack_from("<B", seg_data[seg_idx], pos)
                pos += 1
                f_high = newg & 0x01
                continue
            if f_high:
                take = min(remaining, (len(d) - pos) // 2)
                if take == 0:
                    seg_idx += 1
                    pos = 0
                    (newg,) = struct.unpack_from("<B", seg_data[seg_idx], pos)
                    pos += 1
                    f_high = newg & 0x01
                    continue
                parts.append(d[pos : pos + take * 2].decode("utf-16-le", "replace"))
                pos += take * 2
            else:
                take = min(remaining, len(d) - pos)
                parts.append(d[pos : pos + take].decode("latin-1"))
                pos += take
            remaining -= take
        skip = crun * 4 + cch_ext  # rich-run and phonetic bytes we don't need
        while skip > 0:
            d = seg_data[seg_idx]
            if pos >= len(d):
                seg_idx += 1
                pos = 0
                continue
            take = min(skip, len(d) - pos)
            pos += take
            skip -= take
        strings.append("".join(parts))
    return strings


def _rk_to_number(rk: int) -> float:
    div100 = rk & 1
    value = rk & 0xFFFFFFFC
    if rk & 2:  # 30-bit signed integer
        num = float(struct.unpack("<i", struct.pack("<I", value))[0] >> 2)
    else:  # top 30 bits of an IEEE-754 double
        num = struct.unpack("<d", struct.pack("<Q", value << 32))[0]
    return num / 100.0 if div100 else num


def _fmt_number(num: float) -> str:
    return str(int(num)) if num == int(num) else repr(num)


def _substreams(records: list[tuple[int, bytes]]) -> list[tuple[int, list[tuple[int, bytes]]]]:
    """Разделя BIFF записите на подпотоци (глобален + по един на лист) по ``BOF``/``EOF``."""
    out: list[tuple[int, list[tuple[int, bytes]]]] = []
    dt = 0
    cur: list[tuple[int, bytes]] | None = None
    for rt, data in records:
        if rt == _BOF:
            dt = struct.unpack_from("<H", data, 2)[0] if len(data) >= 4 else 0
            cur = []
        elif rt == _EOF:
            if cur is not None:
                out.append((dt, cur))
                cur = None
        elif cur is not None:
            cur.append((rt, data))
    return out


def _worksheets(records: list[tuple[int, bytes]]) -> list[list[tuple[int, bytes]]]:
    return [recs for dt, recs in _substreams(records) if dt == _SUBSTREAM_WORKSHEET]


def sheet_names(path: str | Path) -> list[str]:
    """Имената на листовете в реда на записите ``BOUNDSHEET`` (глобален подпоток)."""
    records = _records(_Ole2(Path(path).read_bytes()).stream("Workbook"))
    names: list[str] = []
    for rt, data in records:
        if rt == _BOUNDSHEET:
            cch = data[6]
            grbit = data[7]
            if grbit & 1:
                names.append(data[8 : 8 + cch * 2].decode("utf-16-le", "replace"))
            else:
                names.append(data[8 : 8 + cch].decode("latin-1"))
        elif rt == _EOF:  # BOUNDSHEET records live only in the globals substream
            break
    return names


def iter_rows(path: str | Path, sheet: int = 0) -> Iterator[list[str]]:
    """Итерира редовете на даден лист като списъци от низови стойности (по позиция).

    ``sheet`` е индексът измежду работните листове (пропуска глобалния подпоток).
    """
    records = _records(_Ole2(Path(path).read_bytes()).stream("Workbook"))
    strings = _parse_sst(records)
    ws = _worksheets(records)[sheet]
    cells: dict[int, dict[int, str]] = {}
    max_col = -1
    for rt, data in ws:
        if rt == _LABELSST:
            r, c, _xf, isst = struct.unpack_from("<HHHI", data, 0)
            cells.setdefault(r, {})[c] = strings[isst] if isst < len(strings) else ""
            max_col = max(max_col, c)
        elif rt == _LABEL:
            r, c, _xf = struct.unpack_from("<HHH", data, 0)
            cch, grbit = struct.unpack_from("<HB", data, 6)
            if grbit & 1:
                text = data[9 : 9 + cch * 2].decode("utf-16-le", "replace")
            else:
                text = data[9 : 9 + cch].decode("latin-1")
            cells.setdefault(r, {})[c] = text
            max_col = max(max_col, c)
        elif rt == _RK:
            r, c, _xf, rk = struct.unpack_from("<HHHI", data, 0)
            cells.setdefault(r, {})[c] = _fmt_number(_rk_to_number(rk))
            max_col = max(max_col, c)
        elif rt == _MULRK:
            r, col_first = struct.unpack_from("<HH", data, 0)
            (col_last,) = struct.unpack_from("<H", data, len(data) - 2)
            p = 4
            for c in range(col_first, col_last + 1):
                _xf, rk = struct.unpack_from("<HI", data, p)
                p += 6
                cells.setdefault(r, {})[c] = _fmt_number(_rk_to_number(rk))
            max_col = max(max_col, col_last)
        elif rt == _NUMBER:
            r, c, _xf, num = struct.unpack_from("<HHHd", data, 0)
            cells.setdefault(r, {})[c] = _fmt_number(num)
            max_col = max(max_col, c)
    for r in sorted(cells):
        row = cells[r]
        yield [row.get(c, "") for c in range(max_col + 1)]
