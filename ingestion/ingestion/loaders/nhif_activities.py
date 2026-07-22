"""Зареждащ адаптер: месечни експорти на НЗОК „Брой случаи и брой ЗОЛ по КП/АПр/КПр"
→ каноничен ``source.csv`` за приемната тръба.

Реалните данни от титуляря идват като **експорти** (Excel), не като API. Този адаптер е
близкосрочната тръба (режим B, в наши ръце): чете 12-те месечни ``.xlsx``, обединява ги в
**годишен агрегат** при пълна категорийна гранулярност и записва ``source.csv``, който после
минава през същата тръба (схемна валидация → контрол на разкриването → снапшот → DCAT-AP).

Изходни колони на експорта (лист с заглавен ред + хедър):
    РЗОК | Име ЛЗБП | КП/АПр/КПр | Основна диагноза | Вторична диагноза | Брой случаи | Брой ЗОЛ

Канонични колони (source.csv):
    rzok, lzbp, kp_apr_kpr, dg_osnovna, dg_vtorichna, broy_zol, broy_sluchai

Агрегацията сумира ``Брой случаи`` и ``Брой ЗОЛ`` по ключа
(rzok, lzbp, kp_apr_kpr, dg_osnovna, dg_vtorichna) през всички месеци. Контролът на
разкриването е отделна стъпка в тръбата — тук НЕ се потиска нищо.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

from ..xlsx import iter_rows

HEADER_FIRST_CELL = "РЗОК"

# Канонични имена на 28-те РЗОК по код. Източникът е непоследователен между месеците:
# м. 01–05 подават „код + име" (напр. „01 Благоевград"), м. 06–12 само кода („01"). За да не
# се раздвои един и същ регион на два ключа, нормализираме РЗОК до „код + канонично име".
REGIONS: dict[str, str] = {
    "01": "Благоевград",
    "02": "Бургас",
    "03": "Варна",
    "04": "В. Търново",
    "05": "Видин",
    "06": "Враца",
    "07": "Габрово",
    "08": "Добрич",
    "09": "Кърджали",
    "10": "Кюстендил",
    "11": "Ловеч",
    "12": "Монтана",
    "13": "Пазарджик",
    "14": "Перник",
    "15": "Плевен",
    "16": "Пловдив",
    "17": "Разград",
    "18": "Русе",
    "19": "Силистра",
    "20": "Сливен",
    "21": "Смолян",
    "22": "София град",
    "23": "София област",
    "24": "Ст. Загора",
    "25": "Търговище",
    "26": "Хасково",
    "27": "Шумен",
    "28": "Ямбол",
}
FIELDNAMES = [
    "rzok",
    "lzbp",
    "kp_apr_kpr",
    "dg_osnovna",
    "dg_vtorichna",
    "broy_zol",
    "broy_sluchai",
]

Key = tuple[str, str, str, str, str]


def _clean(value: str) -> str:
    return " ".join(value.split())


def _normalize_rzok(value: str) -> str:
    """Нормализира РЗОК до „код + канонично име" независимо от формата на месеца."""
    cleaned = _clean(value)
    match = re.match(r"(\d{1,2})", cleaned)
    if not match:
        return cleaned
    code = match.group(1).zfill(2)
    name = REGIONS.get(code)
    return f"{code} {name}" if name else cleaned


def _int(value: str) -> int:
    value = value.strip()
    if value == "":
        return 0
    return int(float(value.replace(",", ".")))


def _iter_data_rows(path: Path) -> list[list[str]]:
    """Връща само редовете с данни (пропуска заглавен ред и хедъра)."""
    rows: list[list[str]] = []
    started = False
    for cells in iter_rows(path):
        first = _clean(cells[0]) if cells else ""
        if not started:
            if first == HEADER_FIRST_CELL:
                started = True
            continue
        if len(cells) >= 7:
            rows.append(cells[:7])
    if not started:
        raise ValueError(f"{path.name}: не е намерен хедър (клетка '{HEADER_FIRST_CELL}')")
    return rows


def aggregate(input_dir: Path) -> dict[Key, list[int]]:
    """Обединява всички ``*.xlsx`` в директорията в годишен агрегат {ключ: [ЗОЛ, случаи]}."""
    files = sorted(input_dir.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"Няма .xlsx файлове в {input_dir}")
    agg: dict[Key, list[int]] = defaultdict(lambda: [0, 0])
    for path in files:
        count = 0
        for r, lzbp, kp, d1, d2, cases, zol in _iter_data_rows(path):
            key: Key = (
                _normalize_rzok(r),
                _clean(lzbp),
                _clean(kp),
                _clean(d1),
                _clean(d2),
            )
            bucket = agg[key]
            bucket[0] += _int(zol)
            bucket[1] += _int(cases)
            count += 1
        print(f"[loader] {path.name}: {count} реда", file=sys.stderr)
    return agg


def write_source_csv(agg: dict[Key, list[int]], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(FIELDNAMES)
        for key in sorted(agg):
            zol, cases = agg[key]
            writer.writerow([*key, zol, cases])
    return len(agg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nhif-activities-loader",
        description="Месечни НЗОК експорти (.xlsx) → годишен source.csv",
    )
    parser.add_argument("input_dir", type=Path, help="Директория с месечните .xlsx експорти")
    parser.add_argument("out_csv", type=Path, help="Изходен source.csv")
    args = parser.parse_args(argv)

    agg = aggregate(args.input_dir)
    rows = write_source_csv(agg, args.out_csv)
    print(f"✓ {rows} уникални реда записани в {args.out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
