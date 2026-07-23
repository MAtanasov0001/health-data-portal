"""Тестове за рамката за идентичност и route guard-а (режим C)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.auth import (  # noqa: E402
    AuthConfig,
    AuthError,
    DisabledIdentityProvider,
    Principal,
    StaticTokenIdentityProvider,
    build_provider,
    get_identity_provider,
    require_auth,
)
from api.auth.guard import get_auth_config  # noqa: E402

_require_any = require_auth()


def _provider() -> StaticTokenIdentityProvider:
    return StaticTokenIdentityProvider(
        {
            "tok-reader": Principal("reader", scopes=frozenset({"catalog:read"}), mfa=False),
            "tok-admin": Principal(
                "admin", scopes=frozenset({"catalog:read", "catalog:admin"}), mfa=True
            ),
        }
    )


def _app(*, require_mfa: bool = False, scope: str = "catalog:admin") -> FastAPI:
    app = FastAPI()

    @app.get("/protected", dependencies=[Depends(require_auth(scope, require_mfa=require_mfa))])
    def protected() -> dict[str, str]:
        return {"ok": "1"}

    @app.get("/whoami")
    def whoami(principal: Principal = Depends(_require_any)) -> dict[str, str]:
        return {"subject": principal.subject}

    app.dependency_overrides[get_identity_provider] = _provider
    return app


# --- Доставчици ----------------------------------------------------------------------


def test_static_provider_verifies_and_rejects() -> None:
    p = _provider()
    assert p.verify("tok-admin").subject == "admin"
    with pytest.raises(AuthError):
        p.verify("wrong")


def test_from_spec_parses_scopes_and_mfa() -> None:
    p = StaticTokenIdentityProvider.from_spec("t1:alice:a|b:mfa, t2:bob")
    alice = p.verify("t1")
    assert alice.subject == "alice"
    assert alice.scopes == frozenset({"a", "b"})
    assert alice.mfa is True
    bob = p.verify("t2")
    assert bob.scopes == frozenset()
    assert bob.mfa is False


def test_disabled_provider_is_default_and_fails_closed() -> None:
    assert isinstance(build_provider(AuthConfig()), DisabledIdentityProvider)
    with pytest.raises(AuthError):
        build_provider(AuthConfig()).verify("anything")


def test_localdev_backend_selected() -> None:
    provider = build_provider(AuthConfig(backend="localdev", dev_tokens="t:alice:catalog:read"))
    assert isinstance(provider, StaticTokenIdentityProvider)


def test_unknown_backend_not_wired() -> None:
    with pytest.raises(NotImplementedError):
        build_provider(AuthConfig(backend="eid"))


# --- Route guard ---------------------------------------------------------------------


def test_missing_token_401() -> None:
    with TestClient(_app()) as c:
        r = c.get("/protected")
        assert r.status_code == 401
        assert r.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_token_401() -> None:
    with TestClient(_app()) as c:
        r = c.get("/protected", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401


def test_insufficient_scope_403() -> None:
    with TestClient(_app()) as c:
        r = c.get("/protected", headers={"Authorization": "Bearer tok-reader"})
        assert r.status_code == 403


def test_scope_satisfied_200() -> None:
    with TestClient(_app()) as c:
        r = c.get("/protected", headers={"Authorization": "Bearer tok-admin"})
        assert r.status_code == 200


def test_require_mfa_403_without_second_factor() -> None:
    # reader has the scope in this app (scope=catalog:read) but no MFA.
    with TestClient(_app(require_mfa=True, scope="catalog:read")) as c:
        r = c.get("/protected", headers={"Authorization": "Bearer tok-reader"})
        assert r.status_code == 403


def test_principal_injected_into_handler() -> None:
    with TestClient(_app()) as c:
        r = c.get("/whoami", headers={"Authorization": "Bearer tok-admin"})
        assert r.status_code == 200
        assert r.json()["subject"] == "admin"


def test_get_auth_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OHDP_AUTH_BACKEND", "localdev")
    monkeypatch.setenv("OHDP_AUTH_DEV_TOKENS", "t:alice")
    cfg = get_auth_config()
    assert cfg.backend == "localdev"
    assert cfg.dev_tokens == "t:alice"
