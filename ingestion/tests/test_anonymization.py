"""Тестове за псевдонимизацията (чл. 15, ал. 4). Детерминизъм с фиксиран pepper."""

from __future__ import annotations

import pytest

from ingestion.anonymization import (
    AnonymizationError,
    Pseudonymizer,
    PseudonymSpec,
    pseudonymize_rows,
)

_PEPPER = b"fixed-test-pepper-0123456789abcdef"


def _pz(context: str = "dataset-a", **kw: object) -> Pseudonymizer:
    return Pseudonymizer(pepper=_PEPPER, context=context, **kw)  # type: ignore[arg-type]


def test_deterministic_within_context() -> None:
    a = _pz()
    b = _pz()
    assert a.token("EGN-123") == b.token("EGN-123")


def test_unlinkable_across_contexts() -> None:
    # Същият субект в различни набори → различни псевдоними.
    assert _pz("dataset-a").token("EGN-123") != _pz("dataset-b").token("EGN-123")


def test_different_pepper_changes_token() -> None:
    other = Pseudonymizer(pepper=b"another-pepper-abcdef0123456789xy", context="dataset-a")
    assert other.token("EGN-123") != _pz().token("EGN-123")


def test_one_way_and_length() -> None:
    token = _pz().token("EGN-123")
    assert token != "EGN-123"
    assert "EGN-123" not in token
    assert len(token) == 32
    assert all(c in "0123456789abcdef" for c in token)


def test_token_length_configurable() -> None:
    assert len(_pz(token_hex_length=16).token("x")) == 16
    assert len(_pz(token_hex_length=64).token("x")) == 64


def test_normalization_whitespace_and_nfc() -> None:
    assert _pz().token("  EGN-123  ") == _pz().token("EGN-123")
    # NFC: composed and decomposed forms of the same character map equally.
    assert _pz().token("é") == _pz().token("e\u0301")


def test_empty_identifier_rejected() -> None:
    with pytest.raises(AnonymizationError):
        _pz().token("   ")


def test_short_pepper_rejected() -> None:
    with pytest.raises(AnonymizationError):
        Pseudonymizer(pepper=b"short", context="dataset-a")


def test_empty_context_rejected() -> None:
    with pytest.raises(AnonymizationError):
        Pseudonymizer(pepper=_PEPPER, context="  ")


def test_token_length_out_of_bounds_rejected() -> None:
    with pytest.raises(AnonymizationError):
        _pz(token_hex_length=8)
    with pytest.raises(AnonymizationError):
        _pz(token_hex_length=128)


def test_from_env_reads_pepper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OHDP_SECRET_PEPPER", "env-pepper-0123456789abcdef")
    pz = Pseudonymizer.from_env("dataset-a")
    assert len(pz.token("EGN-123")) == 32


def test_from_env_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OHDP_SECRET_PEPPER", raising=False)
    with pytest.raises(AnonymizationError):
        Pseudonymizer.from_env("dataset-a")


def test_pseudonymize_rows_replaces_and_drops() -> None:
    rows: list[dict[str, object]] = [
        {"patient_id": "EGN-1", "internal": "raw", "region": "BG411", "n": 10},
        {"patient_id": "EGN-2", "internal": "raw", "region": "BG341", "n": 7},
    ]
    spec = PseudonymSpec(columns=["patient_id"], drop_columns=["internal"])
    out = pseudonymize_rows(rows, spec, _pz())

    assert rows[0]["patient_id"] == "EGN-1"  # входът не е мутиран
    assert "internal" not in out[0]
    assert out[0]["region"] == "BG411" and out[0]["n"] == 10
    assert out[0]["patient_id"] == _pz().token("EGN-1")
    assert out[0]["patient_id"] != out[1]["patient_id"]


def test_pseudonymize_rows_skips_none() -> None:
    rows: list[dict[str, object]] = [{"patient_id": None, "n": 3}]
    out = pseudonymize_rows(rows, PseudonymSpec(columns=["patient_id"]), _pz())
    assert out[0]["patient_id"] is None
