from collections.abc import Callable
from typing import Annotated

from app.auth import verify_supabase_jwt
from app.permissions import has_permission
from fastapi import Depends, Header, HTTPException, status

__all__ = ["mock_get_current_user", "require_permission"]


def mock_get_current_user(authorization: Annotated[str | None, Header()] = None) -> dict | None:
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
