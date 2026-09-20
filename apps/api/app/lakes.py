from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings

from .auth import get_bearer_token
from .database import supabase

router = APIRouter(prefix="/api/v1", tags=["Catalog"])


def _has_permission(payload: dict, permission: str) -> bool:
    permissions = payload.get("permissions")
    if permissions is None:
        metadata = payload.get("app_metadata") or {}
        permissions = metadata.get("permissions")
    if permissions is None:
        metadata = payload.get("user_metadata") or {}
        permissions = metadata.get("permissions")

    if isinstance(permissions, str):
        permissions = [item.strip() for item in permissions.split(",") if item.strip()]

    if isinstance(permissions, (list, tuple, set)):
        return permission in permissions

    return False


def require_catalog_disable_permission(
    token: str = Depends(get_bearer_token),
) -> dict:
    if not getattr(settings, "supabase_jwt_secret", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La configuración del secreto JWT no está disponible.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1",
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, jwt.PyJWTError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not _has_permission(payload, "catalog:disable"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para desactivar lagos.",
        )

    return payload


@router.get("/lakes")
def list_lakes():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    response = supabase.table("lakes").select("*").neq("status", "inactive").execute()
    return response.data or []


@router.delete("/lakes/{lake_id}")
def disable_lake(
    lake_id: UUID,
    _payload: dict = Depends(require_catalog_disable_permission),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )

    existing = (
        supabase.table("lakes").select("id, status").eq("id", str(lake_id)).execute()
    )
    if not existing.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El lago con id {lake_id} no existe.",
        )

    updated = (
        supabase.table("lakes")
        .update({"status": "inactive"})
        .eq("id", str(lake_id))
        .execute()
    )
    lake = (updated.data or [{}])[0]
    return {
        "id": lake.get("id", str(lake_id)),
        "status": lake.get("status", "inactive"),
        "message": "Lago desactivado correctamente.",
    }
