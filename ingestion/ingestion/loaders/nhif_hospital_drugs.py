"""Зареждащ адаптер: месечни експорти на НЗОК „Справка 5 — ПЛС2" (болнични лекарства —
противотуморни и за вродени коагулопатии, заплащани извън стойността на КП/АПр)
→ каноничен ``source.csv`` за приемната тръба.

Реалните данни идват като **стар двоичен ``.xls``** (OLE2/BIFF8), който четем със
``ingestion.xls`` (само стандартна библиотека). Всеки месец е отделен файл с лист, чийто
хедър започва с клетка „РЦЗ". Адаптерът обединява 12-те месеца в **годишен агрегат** при пълна
категорийна гранулярност и сумира трите мерки. Контролът на разкриването е отделна стъпка в
тръбата — тук НЕ се потиска нищо.

Изходни колони на експорта (15):
    РЦЗ | Наименование на леч.заведение | ATC код | INN | Национален № | НЗОК код |
    Търговско наименование | Лекарствена форма | Колич. на лекарственото в-во |
    Брой в опаковка | МКБ код | Наименование на заболяването |
    Брой на ЗОЛ-броени за периода | Опаковки | Реимбурсна сума

Канонични колони (source.csv): 13 измерения + 3 мерки (broy_zol е обвързваща за разкриването;
opakovki и reimbursna_suma са свързани — скриват се синхронно).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

from ..xls import iter_rows, sheet_names
from .nhif_activities import REGIONS

HEADER_FIRST_CELL = "РЦЗ"
_FACILITY_CODE = re.compile(r"\d{6,}")

FIELDNAMES = [
    "rzok",
    "lz_kod",
    "lz_ime",
    "atc",
    "inn",
    "nacionalen_nomer",
    "nzok_kod",
    "produkt",
    "forma",
    "kolichestvo",
    "broy_v_opakovka",
    "mkb",
    "zabolyavane",
    "broy_zol",
    "opakovki",
    "reimbursna_suma",
]
DIMENSIONS = FIELDNAMES[:13]

Key = tuple[str, ...]


def _clean(value: str) -> str:
    return " ".join(value.split())


def _normalize_rzok(lz_kod: str) -> str:
    """Регион „код + канонично име" от първите две цифри на РЦЗ кода."""
    match = re.match(r"(\d{2})", lz_kod)
    if not match:
        return ""
    code = match.group(1)
    name = REGIONS.get(code)
    return f"{code} {name}" if name else code


def _int(value: str) -> int:
    value = value.strip()
    return int(float(value.replace(",", "."))) if value else 0


def _float(value: str) -> float:
    value = value.strip()
    return float(value.replace(",", ".")) if value else 0.0


def _data_sheet(path: Path) -> int:
    """Индексът на листа с данни (хедър с клетка „РЦЗ"); експортите варират по брой листове."""
    for idx in range(len(sheet_names(path))):
        for n, cells in enumerate(iter_rows(path, sheet=idx)):
            if any(_clean(c) == HEADER_FIRST_CELL for c in cells):
                return idx
            if n >= 5:
                break
    raise ValueError(f"{path.name}: не е намерен лист с хедър (клетка '{HEADER_FIRST_CELL}')")


def _iter_data_rows(path: Path) -> list[list[str]]:
    """Само редовете с данни (пропуска заглавие/хедър/тотали) от листа с данни."""
    rows: list[list[str]] = []
    for cells in iter_rows(path, sheet=_data_sheet(path)):
        if len(cells) >= 15 and _FACILITY_CODE.fullmatch(_clean(cells[0])):
            rows.append(cells[:15])
    return rows


def aggregate(input_dir: Path) -> dict[Key, list[float]]:
    """Обединява всички ``*.xls`` в директорията в годишен агрегат {ключ: [ЗОЛ, опаковки, сума]}."""
    files = sorted(input_dir.glob("*.xls"))
    if not files:
        raise FileNotFoundError(f"Няма .xls файлове в {input_dir}")
    agg: dict[Key, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for path in files:
        count = 0
        for cells in _iter_data_rows(path):
            lz_kod = _clean(cells[0])
            key: Key = (
                _normalize_rzok(lz_kod),
                lz_kod,
                _clean(cells[1]),
                _clean(cells[2]),
                _clean(cells[3]),
                _clean(cells[4]),
                _clean(cells[5]),
                _clean(cells[6]),
                _clean(cells[7]),
                _clean(cells[8]),
                _clean(cells[9]),
                _clean(cells[10]),
                _clean(cells[11]),
            )
            bucket = agg[key]
            bucket[0] += _int(cells[12])
            bucket[1] += _float(cells[13])
            bucket[2] += _float(cells[14])
            count += 1
        print(f"[loader] {path.name}: {count} реда", file=sys.stderr)
    return agg


def write_source_csv(agg: dict[Key, list[float]], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(FIELDNAMES)
        for key in sorted(agg):
            zol, opak, reimb = agg[key]
            writer.writerow([*key, int(zol), round(opak, 3), round(reimb, 2)])
    return len(agg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nhif-hospital-drugs-loader",
        description="Месечни НЗОК експорти (.xls) → годишен source.csv",
    )
    parser.add_argument("input_dir", type=Path, help="Директория с месечните .xls експорти")
    parser.add_argument("out_csv", type=Path, help="Изходен source.csv")
    args = parser.parse_args(argv)

    agg = aggregate(args.input_dir)
    rows = write_source_csv(agg, args.out_csv)
    print(f"✓ {rows} уникални реда записани в {args.out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
