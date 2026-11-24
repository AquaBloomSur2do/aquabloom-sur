from fastapi import APIRouter, Depends, HTTPException, status

from apps.scientific.app.core.database import supabase
from apps.scientific.app.core.dependencies import require_internal_service
from apps.scientific.app.domains.prediction.schemas_prediction import (
    PredictionCreate,
    PredictionResponse,
)
from apps.scientific.app.domains.prediction.service_prediction import (
    create_prediction_service,
)

router = APIRouter(prefix="/api/v1/predictions", tags=["Scientific"])


@router.post(
    "/",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_service)],
)
def create_prediction(payload: PredictionCreate):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return create_prediction_service(supabase, payload)
