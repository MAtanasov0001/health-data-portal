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


def test_count_thousands_separators_normalized():
    rows = [
        {"code": "BG411", "n": "1 234"},
        {"code": "BG341", "n": "1\u00a0234"},
        {"code": "BG231", "n": "1,234"},
    ]
    out = validate_rows(rows, _schema())
    assert [r["n"] for r in out] == [1234, 1234, 1234]


def _decimal_schema() -> DatasetSchema:
    return DatasetSchema(
        columns=[
            ColumnSpec(name="code", type="string", required=True),
            ColumnSpec(name="rate", type="decimal", required=True),
        ],
        disclosure=DisclosureSpec(
            measure_column="rate", dimension_columns=["code"], min_cell_size=5
        ),
    )


def test_decimal_bulgarian_format_normalized():
    rows = [{"code": "BG411", "rate": "1 234,56"}, {"code": "BG341", "rate": "2,5"}]
    out = validate_rows(rows, _decimal_schema())
    assert out[0]["rate"] == 1234.56
    assert out[1]["rate"] == 2.5


def test_missing_column_rejected():
    with pytest.raises(SchemaValidationError):
        validate_rows([{"code": "BG411"}], _schema())


def test_empty_input_rejected():
    with pytest.raises(SchemaValidationError):
        validate_rows([], _schema())
