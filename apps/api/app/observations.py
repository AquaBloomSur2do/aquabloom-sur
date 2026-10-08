from fastapi import APIRouter, HTTPException

from catalog.application.schemas import (
    SpectralObservationCreate,
    SpectralObservationResponse,
)

router = APIRouter(prefix="/api/v1/observations", tags=["Observations"])


@router.post("", response_model=SpectralObservationResponse, status_code=201)
async def create_observation(payload: SpectralObservationCreate):
    """Registra una nueva observación espectral."""
    raise HTTPException(status_code=501, detail="Endpoint en construcción (S2-105)")
