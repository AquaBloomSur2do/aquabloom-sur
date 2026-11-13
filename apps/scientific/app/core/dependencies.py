import secrets
from collections.abc import Callable
from typing import Annotated

from apps.api.app.core.auth import (
    AuthException as SupabaseAuthException,
)
from apps.api.app.core.auth import (
    security,
    verify_supabase_jwt,
)
from apps.api.app.core.config import settings
from apps.api.app.core.permissions import has_permission
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials

__all__ = [
    "mock_get_current_user",
    "require_authenticated_user",
    "require_internal_service",
    "require_permission",
]


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Security(security),  # noqa: B008
) -> dict:
    try:
        return verify_supabase_jwt(credentials)
    except SupabaseAuthException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc


def mock_get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict | None:
    """Mock temporal para evaluar el criterio de aceptación del ticket."""
    if not authorization:
        return None
    if authorization == "Bearer token-admin":
        return {"id": "1", "role": "admin"}
    if authorization == "Bearer token-empleado":
        return {"id": "2", "role": "empleado"}

    return None


def require_permission(required_permission: str) -> Callable:
    """Protege endpoints verificando permisos explícitos o el rol solicitado."""

    def permission_checker(
        payload: Annotated[dict | None, Depends(verify_supabase_jwt)] = None,
    ) -> dict:
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado",
            )
        if not has_permission(payload, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        return payload

    return permission_checker


require_admin = require_permission("admin")


def require_internal_service(
    token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    """Valida la credencial exclusiva para llamadas entre backends."""
    configured_token = settings.internal_service_token
    if configured_token is None or not configured_token.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Autenticación interna no configurada.",
        )
    if token is None or not secrets.compare_digest(
        token, configured_token.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación interna requerida.",
        )
    