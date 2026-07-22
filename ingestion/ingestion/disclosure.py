"""Контрол на разкриването — small-cell suppression.

Ядрото на правната защита: агрегатни клетки с малък брой се потискат, за да не се допусне
реидентификация. Прилага се:

1. **Първично потискане** — всяка клетка с брой под ``min_cell_size`` (или вече маркирана като
   потисната на входа) се потиска.
2. **Вторично потискане** — ако в дадена група (по всяко измерение поотделно) има точно една
   първично потисната клетка, потиска се и следващата най-малка клетка, за да не може стойността
   да се възстанови чрез сумата на групата.

Резултатът заменя стойността на потиснатите клетки с ``None`` и не издава оригиналната стойност.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .models import SUPPRESSED_MARKER, DisclosureSpec


@dataclass
class DisclosureReport:
    min_cell_size: int
    primary_suppressed: int = 0
    secondary_suppressed: int = 0
    total_cells: int = 0
    suppressed_keys: list[str] = field(default_factory=list)

    @property
    def total_suppressed(self) -> int:
        return self.primary_suppressed + self.secondary_suppressed


def apply(
    rows: list[dict[str, Any]], spec: DisclosureSpec
) -> tuple[list[dict[str, Any]], DisclosureReport]:
    """Прилага контрола на разкриването. Връща (нови_редове, отчет). Входът не се мутира."""
    measure = spec.measure_column
    out = [dict(r) for r in rows]
    report = DisclosureReport(min_cell_size=spec.min_cell_size, total_cells=len(out))
    suppressed: set[int] = set()

    # 1. Първично потискане.
    for idx, row in enumerate(out):
        value = row[measure]
        if value == SUPPRESSED_MARKER or (isinstance(value, int) and value < spec.min_cell_size):
            suppressed.add(idx)
    report.primary_suppressed = len(suppressed)

    # 2. Вторично потискане — по всяко измерение поотделно.
    for dim in spec.dimension_columns:
        groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        others = [d for d in spec.dimension_columns if d != dim]
        for idx, row in enumerate(out):
            key = tuple(row[o] for o in others)
            groups[key].append(idx)

        for members in groups.values():
            primary_in_group = [i for i in members if i in suppressed]
            if len(primary_in_group) != 1 or len(members) < 2:
                continue
            candidates = [
                i for i in members if i not in suppressed and isinstance(out[i][measure], int)
            ]
            if not candidates:
                continue
            victim = min(candidates, key=lambda i: out[i][measure])
            suppressed.add(victim)
            report.secondary_suppressed += 1

    for idx in suppressed:
        out[idx][measure] = None
        for linked in spec.linked_measures:
            out[idx][linked] = None
        label = " / ".join(str(out[idx][d]) for d in spec.dimension_columns)
        report.suppressed_keys.append(label)

    return out, report
