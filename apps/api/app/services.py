from uuid import UUID

from supabase import Client

from .repositories import get_active_memberships


def get_current_user_profile(client: Client, user_id: UUID, email: str | None) -> dict:
    return {
        "id": str(user_id),
        "email": email,
        "memberships": get_active_memberships(client, user_id),
    }
