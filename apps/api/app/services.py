from uuid import UUID

from supabase import Client

from .repositories import get_active_memberships


def get_current_user_profile(client: Client, user_id: UUID, email: str | None) -> dict:
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
