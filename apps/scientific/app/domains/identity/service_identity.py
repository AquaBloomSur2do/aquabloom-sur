from uuid import UUID

from apps.scientific.app.domains.identity.model_identity import (
    get_current_user_profile as get_current_user_profile_from_core,
)


def get_current_user_profile(user_id: UUID, email: str | None) -> dict:
    return get_current_user_profile_from_core(user_id, email)
