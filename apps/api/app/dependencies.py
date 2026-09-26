from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth import verify_supabase_jwt


def mock_get_current_user(authorization: Annotated[str | None, Header()] = None) -> dict | None:
    """Mock temporal para evaluar el criterio de aceptación del ticket."""
    if not authorization:
        return None
    if authorization == "Bearer token-admin":
        return {"id": "1", "role": "admin"}
    if authorization == "Bearer token-empleado":
        return {"id": "2", "role": "empleado"}

    return None


def _has_permission(payload: dict, required_permission: str) -> bool:
    metadata = payload.get("user_metadata") or payload.get("app_metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    permissions = payload.get("permissions") or metadata.get("permissions") or []
    if isinstance(permissions, str):
        permissions = [item.strip() for item in permissions.split(",") if item.strip()]

    permission_values = [str(item).strip() for item in permissions if str(item).strip()]
    return required_permission in permission_values


def require_permission(required_permission: str) -> Callable:
    """Protege endpoints verificando que el JWT del usuario tenga el permiso requerido."""

    def permission_checker(payload: dict = Depends(verify_supabase_jwt)) -> dict:
        if not _has_permission(payload, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return payload

    return permission_checker
