from uuid import UUID

from supabase import Client


def get_active_memberships(client: Client, user_id: UUID) -> list[dict]:
    """Return only active memberships belonging to active organizations."""
    response = (
        client.table("memberships")
        .select("id, role, status, organization:organizations!inner(id, name, status)")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .execute()
    )

    return response.data or []


def get_organization_by_id(client: Client, organization_id: UUID) -> dict | None:
    response = (
        client.table("organizations")
        .select("id, name, status, created_at, updated_at")
        .eq("id", str(organization_id))
        .maybe_single()
        .execute()
    )
    return response.data


def get_user_membership_in_organization(
    client: Client, user_id: UUID, organization_id: UUID
) -> dict | None:
    response = (
        client.table("memberships")
        .select("id, user_id, organization_id, role, status, created_at, updated_at")
        .eq("user_id", str(user_id))
        .eq("organization_id", str(organization_id))
        .maybe_single()
        .execute()
    )
    return response.data


def get_organization_members(client: Client, organization_id: UUID) -> list[dict]:
    response = (
        client.table("memberships")
        .select(
            "id, user_id, role, status, created_at, updated_at, "
            "profile:profiles!user_id(id, name, status), "
            "organization:organizations!organization_id(id, name, status)"
        )
        .eq("organization_id", str(organization_id))
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []
