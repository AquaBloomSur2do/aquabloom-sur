from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from apps.scientific.app.core.service_clients import ServiceContractError
from apps.scientific.app.domains.prediction.domain_prediction import (
    build_prediction_detail,
    has_prediction_read_permission,
)
from apps.scientific.app.domains.prediction.model_prediction import (
    get_active_membership_for_organization,
    get_prediction_by_id_in_db,
    get_scene_metadata_in_db,
    insert_prediction_in_db,
)
from apps.scientific.app.domains.prediction.schemas_prediction import (
    PredictionCreate,
    PredictionDetailResponse,
)


def create_prediction_service(client, payload: PredictionCreate) -> dict:
    db_payload = payload.model_dump(mode="json", exclude_none=True)

    try:
        prediction = insert_prediction_in_db(client, db_payload)
    except APIError as exc:
        if getattr(exc, "code", None) == "23503":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró la escena especificada.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo persistir la predicción.",
        ) from exc

    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo persistir la predicción.",
        )
    return prediction


def get_prediction_detail_service(
    client,
    prediction_id: UUID,
    user_id: UUID,
    organization_id: UUID,
    user_payload: dict[str, Any],
) -> PredictionDetailResponse:
    try:
        membership = get_active_membership_for_organization(user_id, organization_id)
    except (APIError, ServiceContractError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudieron verificar los permisos de la organización.",
        ) from exc

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos activos para la organización indicada.",
        )

    if not has_prediction_read_permission(membership, user_payload):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes para consultar el detalle de la estimación.",
        )

    try:
        prediction = get_prediction_by_id_in_db(client, prediction_id, organization_id)
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo consultar el detalle de la estimación.",
        ) from exc

    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la estimación solicitada.",
        )

    scene_metadata = None
    scene_id = prediction.get("scene_id")
    if scene_id is not None:
        try:
            scene_metadata = get_scene_metadata_in_db(UUID(str(scene_id)))
        except ServiceContractError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No se pudo consultar la metadata de la escena en Satellite.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="El identificador de escena almacenado no es válido.",
            ) from exc

    return build_prediction_detail(prediction, scene_row=scene_metadata)
