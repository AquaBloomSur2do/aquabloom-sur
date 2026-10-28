from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import verify_supabase_jwt
from app.database import supabase
from satellite.application.schemas import (
    SpectralObservationCreate,
    SpectralObservationResponse,
)

router = APIRouter(prefix="/api/v1/observations", tags=["Observations"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )
    return supabase


@router.post("", response_model=SpectralObservationResponse, status_code=status.HTTP_201_CREATED)
def create_observation(
    payload: SpectralObservationCreate,
    _token: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    """
    Registra una nueva observación espectral manteniendo la procedencia
    de la escena satelital y la muestra in-situ.
    """
    client = _require_database()

    # Extraer valores para la mutación atómica
    insert_data = {
        "scene_id": str(payload.scene_id),
        "sample_id": str(payload.sample_id),
        "bands": payload.bands,
        "spectral_index": payload.spectral_index,
        "index_value": payload.index_value,
        "unit": payload.unit,
        "quality": payload.quality.value,  # Desempaquetar el Enum
    }

    try:
        response = (
            client.schema("satellite")
            .table("spectral_observations")
            .insert(insert_data)
            .execute()
        )

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se devolvieron datos tras insertar la observación espectral.",
            )

        return response.data[0]

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al guardar la observación espectral: {exc}",
        ) from exc

    