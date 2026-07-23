"""FastAPI route guard — fail-closed зависимост за защита на чувствителни маршрути.

Употреба (за бъдещи защитени операции; публичните четящи маршрути остават без guard)::

    @app.post("/v1/admin/reindex", dependencies=[Depends(require_auth("catalog:admin"))])
    def reindex() -> ...

Guard-ът извлича bearer токен, проверява го през конфигурирания :class:`IdentityProvider`,
след което налага изисквания за MFA и обхвати. Всяка липса → 401/403; никога не пропуска мълчаливо.

Режим C (docs/review-model.md): критичен компонент — подлежи на одит по сигурност.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import AuthError, Principal
from .providers import AuthConfig, IdentityProvider, build_provider

_bearer = HTTPBearer(auto_error=False)


def get_auth_config() -> AuthConfig:
    return AuthConfig.from_env()


def get_identity_provider(config: AuthConfig = Depends(get_auth_config)) -> IdentityProvider:
    return build_provider(config)


def require_auth(
    *scopes: str, require_mfa: bool = False
) -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Връща зависимост, която удостоверява заявката и налага обхвати/MFA."""
    required = frozenset(scopes)

    async def dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        provider: IdentityProvider = Depends(get_identity_provider),
    ) -> Principal:
        if credentials is None or not credentials.credentials:
            raise HTTPException(
                status_code=401,
                detail="изисква се удостоверяване",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            principal = provider.verify(credentials.credentials)
        except AuthError as exc:
            raise HTTPException(
                status_code=401,
                detail="невалидно удостоверение",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        if require_mfa and not principal.mfa:
            raise HTTPException(status_code=403, detail="изисква се втори фактор (MFA)")
        if not principal.has_scopes(required):
            raise HTTPException(status_code=403, detail="недостатъчни права")
        return principal

    return dependency
