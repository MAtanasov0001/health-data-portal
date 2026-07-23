"""Тестове за абстракцията на доставчика на тайни (режим C)."""

from __future__ import annotations

import pytest

from api.security.secrets import (
    EnvSecretProvider,
    SecretNotFound,
    get_secret_provider,
    redact,
)


def test_env_provider_reads_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OHDP_SECRET_PEPPER", "s3cr3t")
    assert EnvSecretProvider().get("pepper") == "s3cr3t"


def test_env_name_normalisation() -> None:
    p = EnvSecretProvider()
    assert p.env_name("pepper") == "OHDP_SECRET_PEPPER"
    assert p.env_name("auth-signing-key") == "OHDP_SECRET_AUTH_SIGNING_KEY"
    assert p.env_name("a.b c") == "OHDP_SECRET_A_B_C"


def test_required_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OHDP_SECRET_ABSENT", raising=False)
    with pytest.raises(SecretNotFound):
        EnvSecretProvider().get("absent")


def test_empty_value_treated_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OHDP_SECRET_BLANK", "")
    with pytest.raises(SecretNotFound):
        EnvSecretProvider().get("blank")


def test_optional_missing_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OHDP_SECRET_OPT", raising=False)
    assert EnvSecretProvider().get("opt", required=False) is None
    assert EnvSecretProvider().get("opt", required=False, default="fallback") == "fallback"


def test_factory_default_is_env() -> None:
    assert isinstance(get_secret_provider("env"), EnvSecretProvider)


def test_factory_unknown_backend_not_wired() -> None:
    with pytest.raises(NotImplementedError):
        get_secret_provider("vault")


def test_redact_never_reveals() -> None:
    secret = "super-secret-value"
    assert secret not in redact(secret)
    assert secret not in redact(secret, keep=4)
    assert redact(secret, keep=4).startswith("supe")
    assert redact("") == "<empty>"
    assert redact(None) == "<empty>"
