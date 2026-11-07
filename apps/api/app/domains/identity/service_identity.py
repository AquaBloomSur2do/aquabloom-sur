from uuid import UUID

from fastapi import HTTPException, status

from apps.api.app.domains.identity.model_identity import (
    count_active_lakes,
    count_active_stations,
    count_visible_organizations,
    get_active_membership_for_user,
    get_active_memberships,
    get_organization_by_id,
    get_profiles_by_ids,
    insert_audit_log,
    insert_membership,
    insert_organization,
    is_admin_in_other_organization,
    list_all_profiles_ordered,
    list_organization_memberships,
    list_user_organizations_from_db,
    membership_exists,
    profile_exists,
    upsert_user_profile,
)
from apps.api.app.domains.identity.schemas_identity import DashboardSummaryResponse
from supabase import Client


def get_dashboard_summary(
    supabase: Client, user_data: dict
) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        active_lakes_count=count_active_lakes(supabase),
        active_stations_count=count_active_stations(supabase),
        visible_organizations_count=count_visible_organizations(supabase, user_data),
    )


def get_all_profiles_service(supabase: Client) -> list[dict]:
    return list_all_profiles_ordered(supabase)


def get_user_organizations_service(supabase: Client, user_id: str) -> list[dict]:
    return list_user_organizations_from_db(supabase, user_id)


def get_current_user_profile(client: Client, user_id: UUID, email: str | None) -> dict:
    upsert_user_profile(client, user_id, email)
    return {
        "id": str(user_id),
        "email": email,
        "memberships": get_active_memberships(client, user_id),
    }


def get_organization_members_for_user(
    client: Client, user_id: UUID, organization_id: UUID
) -> list[dict]:
    organization = get_organization_by_id(client, organization_id)
    if not organization:
        raise LookupError(f"Organización no encontrada: {organization_id}")

    requester_membership = get_active_membership_for_user(
        client, user_id, organization_id
    )
    if not requester_membership:
        raise PermissionError("Usuario no pertenece a la organización")

    members = list_organization_memberships(client, organization_id)
    user_ids = list({str(member["user_id"]) for member in members})
    profiles = get_profiles_by_ids(client, user_ids)
    profiles_by_id = {str(profile["id"]): profile for profile in profiles}

    return [
        {
            "user_id": UUID(str(member["user_id"])),
            "profile_id": UUID(str(member["user_id"])),
            "full_name": profiles_by_id.get(str(member["user_id"]), {}).get("name"),
            "email": profiles_by_id.get(str(member["user_id"]), {}).get("email"),
            "role": member["role"],
            "status": member["status"],
            "created_at": member["created_at"],
            "updated_at": member["updated_at"],
        }
        for member in members
    ]


def add_organization_member(
    supabase: Client, org_id: UUID, profile_id: UUID, role: str, requester_user_id: UUID
) -> dict:
    requester_membership = get_active_membership_for_user(
        supabase, requester_user_id, org_id
    )
    if not requester_membership or requester_membership.get("role") != "admin":
        raise PermissionError(
            "Solo un administrador activo de la organización puede agregar miembros."
        )

    if not profile_exists(supabase, profile_id):
        raise LookupError("Perfil inexistente")

    if membership_exists(supabase, org_id, profile_id):
        raise ValueError("Membresia duplicada en esta organización")

    if role == "admin" and is_admin_in_other_organization(supabase, profile_id, org_id):
        raise ValueError("El usuario ya es administrador de otra organización")

    return insert_membership(supabase, org_id, profile_id, role)


def create_organization(supabase: Client, org_data: dict) -> dict:
    try:
        return insert_organization(supabase, org_data)
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


def create_organization_with_admin(
    supabase: Client, org_data: dict, creator_user_id: str
) -> dict:
    organization = create_organization(supabase, org_data)
    insert_membership(supabase, UUID(str(organization["id"])), UUID(creator_user_id), "admin")
    return organization


def log_audit_event(
    supabase: Client,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> None:
    """Registra un evento de auditoría sin bloquear la transacción principal HTTP."""
    insert_audit_log(supabase, actor_id, action, resource_type, resource_id, details)
