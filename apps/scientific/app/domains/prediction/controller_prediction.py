from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from apps.scientific.app.core.database import supabase
from apps.scientific.app.core.dependencies import (
    require_authenticated_user,
    require_internal_service,
)
from apps.scientific.app.domains.prediction.schemas_prediction import (
    PredictionCreate,
    PredictionDetailResponse,
    PredictionResponse,
)
from apps.scientific.app.domains.prediction.service_prediction import (
    create_prediction_service,
    get_prediction_detail_service,
)

router = APIRouter(prefix="/api/v1/predictions", tags=["Scientific"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


def _extract_user_id(user: dict[str, Any]) -> UUID:
    try:
        return UUID(str(user.get("sub")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario válido.",
        ) from exc


@router.post(
    "/",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_service)],
)
def create_prediction(payload: PredictionCreate):
    client = _require_database()
    return create_prediction_service(client, payload)


@router.get(
    "/{prediction_id}",
    response_model=PredictionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Exponer detalle completo de una estimación científica",
)
def get_prediction_detail(
    prediction_id: UUID,
    organization_id: Annotated[UUID, Header(alias="X-Organization-ID")],
    user: Annotated[dict[str, Any], Depends(require_authenticated_user)],
):
    client = _require_database()
    user_id = _extract_user_id(user)
    return get_prediction_detail_service(
        client,
        prediction_id=prediction_id,
        user_id=user_id,
        organization_id=organization_id,
        user_payload=user,
    )


