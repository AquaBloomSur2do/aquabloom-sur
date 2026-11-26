from uuid import UUID

from apps.scientific.app.core.service_clients import CoreServiceClient


def get_current_user_profile(user_id: UUID, email: str | None) -> dict:
    """Obtiene el perfil y las membresías mediante el contrato interno de Core."""
    return CoreServiceClient().get_current_user_profile(user_id, email)
