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


