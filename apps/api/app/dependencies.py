from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth import require_admin

__all__ = ["mock_get_current_user", "require_admin", "require_permission"]


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


def require_permission(required_role: str) -> Callable:
    """Crea una dependencia que exige un rol o un alias equivalente."""
    normalized_required_role = _normalize_role(required_role)
    allowed_roles = {
        normalized_required_role,
        "administrador" if normalized_required_role == "admin" else "admin",
    }

    def role_checker(
        current_user: Annotated[dict | None, Depends(verify_supabase_jwt)] = None,
    ) -> dict:
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado",
            )

        role = current_user.get("role") or (
            current_user.get("user_metadata") or {}
        ).get("role")
        if _normalize_role(role) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )

        return current_user

    return role_checker


require_admin = require_permission("administrador")
