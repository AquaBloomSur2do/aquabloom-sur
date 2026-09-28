from uuid import UUID

from fastapi import HTTPException, status
from shapely.geometry import Point, shape
from supabase import Client

from .repositories import get_active_memberships

from app.repositories import get_lake_by_id as get_active_lake_by_id
from app.repositories import soft_delete_lake


def validate_station_inside_lake(lake_geojson: dict, lat: float, lon: float) -> None:
    station_point = Point(lon, lat)
    lake_polygon = shape(lake_geojson)

    if not lake_polygon.contains(station_point):
        raise ValueError("Las coordenadas de la estación están fuera del polígono del lago.")


def get_current_user_profile(client: Client, user_id: UUID, email: str | None) -> dict:
    try:
        client.table("profiles").upsert(
            {"id": str(user_id), "email": email},
            on_conflict="id",
        ).execute()
    except Exception:  # noqa: BLE001, S110
        pass

    return {
        "id": str(user_id),
        "email": email,
        "memberships": get_active_memberships(client, user_id),
    }


def get_organization_members_for_user(
    client: Client, user_id: UUID, organization_id: UUID
) -> list[dict]:
    organization = (
        client.table("organizations")
        .select("id, name, status")
        .eq("id", str(organization_id))
        .maybe_single()
        .execute()
    )
    if not organization.data:
        raise LookupError(f"Organización no encontrada: {organization_id}")

    requester_membership = (
        client.table("memberships")
        .select("id, role, status")
        .eq("user_id", str(user_id))
        .eq("organization_id", str(organization_id))
        .maybe_single()
        .execute()
    )
    if not requester_membership.data:
        raise PermissionError("Usuario no pertenece a la organización")

    response = (
        client.table("memberships")
        .select(
            "id, user_id, role, status, created_at, updated_at, "
            "profile:profiles!user_id(id, email, full_name)"
        )
        .eq("organization_id", str(organization_id))
        .order("created_at", desc=False)
        .execute()
    )

    members = response.data or []
    return [
        {
            "user_id": UUID(str(member["user_id"])),
            "profile_id": (
                UUID(str(member["profile"]["id"]))
                if member.get("profile") and member["profile"].get("id")
                else None
            ),
            "full_name": (
                member.get("profile", {}).get("full_name")
                if member.get("profile")
                else None
            ),
            "email": (
                member.get("profile", {}).get("email")
                if member.get("profile")
                else None
            ),
            "role": member["role"],
            "status": member["status"],
            "created_at": member["created_at"],
            "updated_at": member["updated_at"],
        }
        for member in members
    ]


def add_organization_member(supabase, org_id: UUID, profile_id: UUID, role: str) -> dict:
    profile_res = supabase.table("profiles").select("id").eq("id", str(profile_id)).execute()
    if not profile_res.data:
        raise LookupError("Perfil inexistente")

    member_res = (
        supabase.table("memberships")
        .select("id")
        .eq("organization_id", str(org_id))
        .eq("profile_id", str(profile_id))
        .execute()
    )
    if member_res.data:
        raise ValueError("Membresia duplicada en esta organización")

    if role == "admin":
        admin_res = (
            supabase.table("memberships")
            .select("id")
            .eq("profile_id", str(profile_id))
            .eq("role", "admin")
            .neq("organization_id", str(org_id))
            .execute()
        )
        if admin_res.data:
            raise ValueError("El usuario ya es administrador de otra organización")

    insert_res = (
        supabase.table("memberships")
        .insert(
            {
                "organization_id": str(org_id),
                "profile_id": str(profile_id),
                "role": role,
                "status": "active",
            }
        )
        .execute()
    )

    return insert_res.data[0]


def get_lake_by_id(supabase, lake_id: UUID) -> dict:
    response = supabase.table("lakes").select("*").eq("id", str(lake_id)).execute()

    if not response.data:
        raise LookupError("Lago no encontrado")
    return response.data[0]


def create_organization(supabase, org_data: dict) -> dict:
    try:
        response = supabase.table("organizations").insert(org_data).execute()
        return response.data[0]
    except Exception as exc:
        error_msg = str(exc).lower()
        if (
            "duplicate key" in error_msg
            or "unique constraint" in error_msg
            or "23505" in error_msg
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una organización con ese identificador o nombre.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear la organización: {exc!s}",
        ) from exc


def log_audit_event(supabase, actor_id: str, action: str, resource_type: str, resource_id: str, details: dict | None = None) -> None:
    """Registra un evento de auditoría sin bloquear la transacción principal HTTP."""
    try:
        supabase.table("audit_logs").insert({
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "details": details or {}
        }).execute()
    except Exception as e:  # noqa: BLE001
        print(f"Alerta: Fallo silencioso en auditoría: {e}")