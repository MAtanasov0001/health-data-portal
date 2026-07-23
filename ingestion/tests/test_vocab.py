import pytest
from pydantic import ValidationError

from ingestion import vocab
from ingestion.models import DatasetMetadata


def _metadata(**overrides):
    base = dict(
        identifier="test-set",
        title={"bg": "Тест"},
        description={"bg": "Описание"},
        publisher="МЗ",
        contact_email="data@example.bg",
        theme=["HEAL"],
        accrual_periodicity="ANNUAL",
        spatial=["BG"],
        access_rights="PUBLIC",
        license="CC-BY-4.0",
    )
    base.update(overrides)
    return base


def test_valid_codes_accepted():
    md = DatasetMetadata(**_metadata())
    assert md.theme == ["HEAL"]
    assert md.license == "CC-BY-4.0"


@pytest.mark.parametrize(
    "field,value",
    [
        ("theme", ["HEALTH"]),
        ("accrual_periodicity", "YEARLY"),
        ("access_rights", "OPEN"),
        ("license", "MIT"),
        ("spatial", ["FR"]),
    ],
)
def test_unknown_code_rejected(field, value):
    with pytest.raises(ValidationError):
        DatasetMetadata(**_metadata(**{field: value}))


def test_check_functions_reject_directly():
    with pytest.raises(ValueError):
        vocab.check_theme(["NOPE"])
    with pytest.raises(ValueError):
        vocab.check_frequency("FORTNIGHTLY")
    with pytest.raises(ValueError):
        vocab.check_access_right("SECRET")
    with pytest.raises(ValueError):
        vocab.check_license("Apache-2.0")
    with pytest.raises(ValueError):
        vocab.check_spatial(["BG3111"])


def test_license_uri_is_single_source_of_truth():
    assert set(vocab.LICENSES) == set(vocab.LICENSE_URI)
    for code in vocab.LICENSES:
        assert vocab.LICENSE_URI[code].startswith("http")


def test_nuts_bg_bounds():
    assert vocab.check_spatial(["BG", "BG3", "BG34", "BG411"]) == ["BG", "BG3", "BG34", "BG411"]
    with pytest.raises(ValueError):
        vocab.check_spatial(["DE"])
