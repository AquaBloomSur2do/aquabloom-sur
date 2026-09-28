from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth import verify_supabase_jwt

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


def _normalize_role(role: str | None) -> str:
    return str(role or "").strip().lower()


def _has_permission(current_user: dict | None, required_permission: str) -> bool:
    if not current_user:
        return False

    sources = [current_user]
    for key in ("user_metadata", "app_metadata"):
        metadata = current_user.get(key)
        if isinstance(metadata, dict):
            sources.append(metadata)

    roles = {
        _normalize_role(source.get("role"))
        for source in sources
        if source.get("role")
    }
    normalized_required = _normalize_role(required_permission)
    if normalized_required in roles:
        return True
    if normalized_required in {"admin", "administrador"} and roles.intersection(
        {"admin", "administrador"}
    ):
        return True

    permissions = []
    for source in sources:
        value = source.get("permissions")
        if isinstance(value, str):
            permissions.extend(value.split(","))
        elif isinstance(value, (list, tuple, set)):
            permissions.extend(value)

    permission_values = {
        str(item).strip() for item in permissions if str(item).strip()
    }
    return required_permission in permission_values


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
        if not _has_permission(payload, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        return payload

    return permission_checker


require_admin = require_permission("admin")
