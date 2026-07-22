"""Схема на набора и на входа: зареждане на metadata.yaml / schema.yaml и валидация на редове.

Валидацията е строга: файл, който не отговаря на схемата, се отхвърля (не се приема частично).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

SUPPRESSED_MARKER = "<5"


class ColumnSpec(BaseModel):
    """Спецификация на една колона от schema.yaml."""

    name: str
    type: Literal["string", "count", "count_or_suppressed"]
    required: bool = True
    pattern: str | None = None
    description: str | None = None


class DisclosureSpec(BaseModel):
    """Кои колони са мерки/измерения и какъв е минималният размер на клетка."""

    measure_column: str
    dimension_columns: list[str]
    min_cell_size: int = Field(ge=1)


class DatasetSchema(BaseModel):
    """Съдържанието на schema.yaml."""

    columns: list[ColumnSpec]
    disclosure: DisclosureSpec

    @classmethod
    def from_yaml(cls, path: Path) -> DatasetSchema:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def column(self, name: str) -> ColumnSpec:
        for col in self.columns:
            if col.name == name:
                return col
        raise KeyError(f"Няма колона '{name}' в схемата")


class TemporalMeta(BaseModel):
    start: str
    end: str


class ProvenanceMeta(BaseModel):
    bg: str
    en: str | None = None


class DatasetMetadata(BaseModel):
    """Съдържанието на metadata.yaml — попълва DCAT-AP профила."""

    identifier: str
    title: dict[str, str]
    description: dict[str, str]
    publisher: str
    contact_email: str
    theme: list[str]
    keyword: dict[str, list[str]] = Field(default_factory=dict)
    accrual_periodicity: str | None = None
    spatial: list[str] = Field(default_factory=list)
    temporal: TemporalMeta | None = None
    access_rights: str = "PUBLIC"
    license: str = "CC-BY-4.0"
    provenance: ProvenanceMeta | None = None
    version: str = "1.0.0"

    @field_validator("identifier")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", v):
            raise ValueError("identifier трябва да е slug: малки букви, цифри и тире")
        return v

    @classmethod
    def from_yaml(cls, path: Path) -> DatasetMetadata:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)


class SchemaValidationError(ValueError):
    """Входът не отговаря на схемата."""


def validate_rows(rows: list[dict[str, str]], schema: DatasetSchema) -> list[dict[str, Any]]:
    """Валидира редовете спрямо схемата; връща нормализирани редове или вдига грешка.

    Мерната колона се нормализира: число → int; маркерът за потискане остава като SUPPRESSED_MARKER.
    """
    if not rows:
        raise SchemaValidationError("Празен вход")

    expected = {c.name for c in schema.columns}
    normalized: list[dict[str, Any]] = []

    for i, row in enumerate(rows, start=1):
        missing = {c.name for c in schema.columns if c.required} - set(row)
        if missing:
            raise SchemaValidationError(f"Ред {i}: липсват колони {sorted(missing)}")
        extra = set(row) - expected
        if extra:
            raise SchemaValidationError(f"Ред {i}: непознати колони {sorted(extra)}")

        out: dict[str, Any] = {}
        for col in schema.columns:
            raw = (row.get(col.name) or "").strip()
            if col.required and raw == "":
                raise SchemaValidationError(f"Ред {i}: празна стойност за '{col.name}'")
            if col.pattern and raw and not re.fullmatch(col.pattern, raw):
                raise SchemaValidationError(
                    f"Ред {i}: '{col.name}'='{raw}' не отговаря на образеца {col.pattern}"
                )
            out[col.name] = _coerce(raw, col, row_no=i)
        normalized.append(out)

    return normalized


def _coerce(raw: str, col: ColumnSpec, *, row_no: int) -> Any:
    if col.type == "string":
        return raw
    if col.type in ("count", "count_or_suppressed"):
        if raw == SUPPRESSED_MARKER and col.type == "count_or_suppressed":
            return SUPPRESSED_MARKER
        try:
            value = int(raw)
        except ValueError as exc:
            raise SchemaValidationError(
                f"Ред {row_no}: '{col.name}'='{raw}' не е цяло число"
            ) from exc
        if value < 0:
            raise SchemaValidationError(f"Ред {row_no}: '{col.name}' е отрицателно")
        return value
    raise SchemaValidationError(f"Непознат тип колона: {col.type}")
