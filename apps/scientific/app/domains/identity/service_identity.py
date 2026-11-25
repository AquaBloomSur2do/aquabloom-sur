from uuid import UUID

from apps.scientific.app.domains.identity.model_identity import (
    get_active_memberships,
    upsert_user_profile,
)
from supabase import Client


def get_current_user_profile(
    client: Client, user_id: UUID, email: str | None
) -> dict:
    upsert_user_profile(client, user_id, email)
    return {
        "id": str(user_id),
        "email": email,
        "memberships": get_active_memberships(client, user_id),
    }
