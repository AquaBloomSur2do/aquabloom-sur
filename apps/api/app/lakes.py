from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security, status

from .auth import verify_supabase_jwt
from .database import supabase

router = APIRouter(prefix="/api/v1", tags=["Catalog"])


def _get_permissions(payload: dict) -> list[str]:
    permissions = payload.get("permissions", [])
    if not permissions:
        permissions = (payload.get("app_metadata") or {}).get("permissions", [])
    if not permissions:
        permissions = (payload.get("user_metadata") or {}).get("permissions", [])

    if isinstance(permissions, str):
        permissions = [item.strip() for item in permissions.split(",") if item.strip()]

    if isinstance(permissions, (list, tuple, set)):
        return [str(item).strip() for item in permissions if str(item).strip()]

    return []


def _get_role(payload: dict) -> str:
    role = (
        payload.get("role")
        or (payload.get("app_metadata") or {}).get("role")
        or (payload.get("user_metadata") or {}).get("role")
        or ""
    )
    return str(role).lower()


def _has_permission(payload: dict, permission: str) -> bool:
    return permission in _get_permissions(payload)


def require_catalog_disable_permission(
    payload: dict = Security(verify_supabase_jwt),  # noqa: B008
) -> dict:
    role = _get_role(payload)
    permissions = _get_permissions(payload)
    status_value = str(
        payload.get("status")
        or (payload.get("app_metadata") or {}).get("status")
        or (payload.get("user_metadata") or {}).get("status")
        or "active"
    ).lower()

    if status_value and status_value != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para desactivar lagos.",
        )

    if role in {"administrator", "curator"} or "catalog:disable" in permissions:
        return payload

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permisos para desactivar lagos.",
    )


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
