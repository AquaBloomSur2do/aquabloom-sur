from uuid import UUID

from supabase import Client


def get_active_memberships(client: Client, user_id: UUID) -> list[dict]:
    """Obtiene membresías activas de organizaciones activas."""
    response = (
        client.table("memberships")
        .select("id, role, status, organization:organizations!inner(id, name, status)")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .execute()
    )
    return response.data or []


def upsert_user_profile(client: Client, user_id: UUID, email: str | None) -> None:
    client.table("profiles").upsert(
        {"id": str(user_id), "email": email},
        on_conflict="id",
        ignore_duplicates=True,
    ).execute()
