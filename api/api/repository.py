"""Хранилище само за четене над снапшотите, произведени от приемната тръба.

Само стандартна библиотека — четем неизменяемите снапшоти от диска:
``<root>/<identifier>/<version>/{manifest.json, data.csv, dcat.jsonld}``.
"""

from __future__ import annotations

import csv
import itertools
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DatasetVersion:
    identifier: str
    version: str
    created_at: str
    checksum_sha256: str
    row_count: int
    path: Path

    @property
    def manifest(self) -> dict[str, Any]:
        return json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))

    @property
    def dcat(self) -> dict[str, Any]:
        return json.loads((self.path / "dcat.jsonld").read_text(encoding="utf-8"))

    @property
    def collection(self) -> dict[str, Any] | None:
        """Метаданни за колекцията (група таблици), ако наборът е член на такава — иначе ``None``."""
        value = self.manifest.get("collection")
        return value if isinstance(value, dict) else None

    @property
    def dimensions(self) -> list[str]:
        """Категорийни колони (за избор на измерение във визуализацията)."""
        return list(self.manifest.get("dimensions", []))

    @property
    def measures(self) -> list[str]:
        """Числови колони (за избор на мярка във визуализацията)."""
        return list(self.manifest.get("measures", []))

    def data_csv(self) -> str:
        return (self.path / "data.csv").read_text(encoding="utf-8")

    def data_page(self, offset: int, limit: int) -> tuple[list[str], list[list[str]]]:
        """Чете хедъра + прозорец от ``limit`` реда след ``offset`` без да зарежда целия файл.

        Пропуснатите редове се итерират, но не се материализират — памет-леко за големи набори
        (напр. ~593 хил. реда), за да е практична пагинацията (МЕ90) към frontend/харвестъри.
        """
        with (self.path / "data.csv").open(encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            window = list(itertools.islice(reader, offset, offset + limit))
        return header, window

    def iter_data(self) -> Iterator[list[str]]:
        """Итерира редовете на снапшота (пръв ред = хедър) поточно, за пълен експорт (XLSX)."""
        with (self.path / "data.csv").open(encoding="utf-8", newline="") as fh:
            yield from csv.reader(fh)

    def aggregate(self, dimension: str, measure: str, top: int) -> list[tuple[str, float, int]]:
        """Групира по ``dimension`` и сумира числовата ``measure``; връща топ-``top`` групи.

        Потиснатите клетки (празни) и нечисловите стойности се пропускат — агрегатът е върху
        вече контролираните данни, затова е безопасен за публична визуализация.
        """
        with (self.path / "data.csv").open(encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader, [])
            di, mi = header.index(dimension), header.index(measure)
            sums: dict[str, float] = {}
            counts: dict[str, int] = {}
            for row in reader:
                if di >= len(row) or mi >= len(row) or row[mi] == "":
                    continue
                try:
                    val = float(row[mi])
                except ValueError:
                    continue
                key = row[di]
                sums[key] = sums.get(key, 0.0) + val
                counts[key] = counts.get(key, 0) + 1
        ranked = sorted(sums, key=lambda k: sums[k], reverse=True)[:top]
        return [(k, sums[k], counts[k]) for k in ranked]


def _semver_key(version: str) -> tuple[int, ...]:
    parts = []
    for p in version.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


class Repository:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _versions(self, identifier: str) -> list[DatasetVersion]:
        ds_dir = self.root / identifier
        if not ds_dir.is_dir():
            return []
        out: list[DatasetVersion] = []
        for vdir in ds_dir.iterdir():
            manifest_path = vdir / "manifest.json"
            if not manifest_path.is_file():
                continue
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            out.append(
                DatasetVersion(
                    identifier=identifier,
                    version=m["version"],
                    created_at=m["created_at"],
                    checksum_sha256=m["checksum_sha256"],
                    row_count=m["row_count"],
                    path=vdir,
                )
            )
        out.sort(key=lambda dv: _semver_key(dv.version), reverse=True)
        return out

    def identifiers(self) -> list[str]:
        if not self.root.is_dir():
            return []
        ids = [p.name for p in self.root.iterdir() if p.is_dir() and self._versions(p.name)]
        return sorted(ids)

    def latest(self, identifier: str) -> DatasetVersion | None:
        versions = self._versions(identifier)
        return versions[0] if versions else None

    def get(self, identifier: str, version: str | None = None) -> DatasetVersion | None:
        if version is None:
            return self.latest(identifier)
        for dv in self._versions(identifier):
            if dv.version == version:
                return dv
        return None

    def list_latest(self) -> list[DatasetVersion]:
        result = [self.latest(i) for i in self.identifiers()]
        items = [dv for dv in result if dv is not None]
        items.sort(key=lambda dv: dv.identifier)
        return items

    def collection_members(self, collection_id: str) -> list[DatasetVersion]:
        """Най-новите версии на всички таблици, чийто манифест сочи ``collection.id``."""
        members = [
            dv
            for dv in self.list_latest()
            if (dv.collection or {}).get("id") == collection_id
        ]
        members.sort(key=lambda dv: dv.identifier)
        return members

    def collections(self) -> dict[str, list[DatasetVersion]]:
        """Групира най-новите набори по идентификатор на колекция (само тези с колекция)."""
        groups: dict[str, list[DatasetVersion]] = {}
        for dv in self.list_latest():
            coll = dv.collection
            if not coll:
                continue
            cid = str(coll.get("id"))
            groups.setdefault(cid, []).append(dv)
        for members in groups.values():
            members.sort(key=lambda dv: dv.identifier)
        return groups
