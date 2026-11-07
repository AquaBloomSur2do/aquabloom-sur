from uuid import UUID

from apps.satellite.app.core.auth import verify_supabase_jwt
from apps.satellite.app.core.database import supabase
from apps.satellite.app.domains.observations.schemas_observations import (
    SpectralObservationCreate,
    SpectralObservationResponse,
)
from apps.satellite.app.domains.observations.service_observations import (
    create_observation_service,
    extract_observation_user_id,
    get_observations_service,
)
from fastapi import APIRouter, Depends, HTTPException, Query, status

router = APIRouter(prefix="/api/v1/observations", tags=["Observations"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BD no disponible",
        )
    return supabase


@router.post(
    "",
    response_model=SpectralObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_observation(
    payload: SpectralObservationCreate,
    _token: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Registra una nueva observación espectral (Integrado desde S2-127)."""
    client = _require_database()
    user_id = extract_observation_user_id(_token)
    return create_observation_service(client, payload, user_id)


@router.get(
    "",
    response_model=list[SpectralObservationResponse],
    status_code=status.HTTP_200_OK,
)
def get_observations(
    scene_id: UUID = Query(..., description="ID de la escena"),  # noqa: B008
    sample_id: UUID = Query(..., description="ID de la muestra"),  # noqa: B008
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """Endpoint GET Piloto S2-128 con Fallback Inteligente."""
    client = _require_database()
    user_id = extract_observation_user_id(payload)
    return get_observations_service(client, scene_id, sample_id, user_id)

