from uuid import UUID

from supabase import Client

from .repositories import (
    get_active_memberships,
    get_organization_by_id,
    get_organization_members,
    get_user_membership_in_organization,
)


def get_current_user_profile(client: Client, user_id: UUID, email: str | None) -> dict:
    return {
        "id": str(user_id),
        "email": email,
        "memberships": get_active_memberships(client, user_id),
    }


def get_organization_members_for_user(
    client: Client, user_id: UUID, organization_id: UUID
) -> list[dict]:
    organization = get_organization_by_id(client, organization_id)
    if organization is None:
        raise LookupError(f"La organización {organization_id} no existe.")

    if organization.get("status") != "active":
        raise PermissionError(
            "La organización no está activa para realizar esta consulta."
        )

    membership = get_user_membership_in_organization(client, user_id, organization_id)
    if membership is None or membership.get("status") != "active":
        raise PermissionError(
            "No tienes permisos para consultar los miembros de esta organización."
        )

    members = get_organization_members(client, organization_id)
    user_ids = {str(member["user_id"]) for member in members if member.get("user_id")}
    email_by_user_id: dict[str, str | None] = {}

    if user_ids:
        try:
            users_response = client.auth.admin.list_users()
            for user in users_response.users:
                if getattr(user, "id", None) is not None:
                    email_by_user_id[str(user.id)] = getattr(user, "email", None)
        except (AttributeError, TypeError):
            email_by_user_id = {}

    normalized_members: list[dict] = []
    for member in members:
        profile = member.get("profile") or {}
        user_id_value = member.get("user_id")
        normalized_member = {
            "user_id": UUID(str(user_id_value)),
            "profile_id": (
                UUID(str(profile["id"]))
                if isinstance(profile, dict) and profile.get("id")
                else None
            ),
            "full_name": profile.get("name") if isinstance(profile, dict) else None,
            "email": email_by_user_id.get(str(user_id_value)),
            "role": member.get("role"),
            "status": member.get("status"),
            "created_at": member.get("created_at"),
            "updated_at": member.get("updated_at"),
        }
        normalized_members.append(normalized_member)

    return normalized_members
