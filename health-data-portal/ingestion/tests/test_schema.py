import pytest

from ingestion.models import (
    ColumnSpec,
    DatasetSchema,
    DisclosureSpec,
    SchemaValidationError,
    validate_rows,
)


def _schema() -> DatasetSchema:
    return DatasetSchema(
        columns=[
            ColumnSpec(name="code", type="string", required=True, pattern=r"^BG[0-9]{3}$"),
            ColumnSpec(name="n", type="count_or_suppressed", required=True),
        ],
        disclosure=DisclosureSpec(measure_column="n", dimension_columns=["code"], min_cell_size=5),
    )


def test_valid_rows_normalized():
    rows = [{"code": "BG411", "n": "10"}, {"code": "BG341", "n": "<5"}]
    out = validate_rows(rows, _schema())
    assert out[0]["n"] == 10
    assert out[1]["n"] == "<5"


def test_pattern_violation_rejected():
    with pytest.raises(SchemaValidationError):
        validate_rows([{"code": "XX1", "n": "10"}], _schema())


def test_negative_count_rejected():
    with pytest.raises(SchemaValidationError):
        validate_rows([{"code": "BG411", "n": "-1"}], _schema())


def test_missing_column_rejected():
    with pytest.raises(SchemaValidationError):
        validate_rows([{"code": "BG411"}], _schema())


def test_empty_input_rejected():
    with pytest.raises(SchemaValidationError):
        validate_rows([], _schema())
