from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from apps.scientific.app.domains.prediction.domain_prediction import (
    build_prediction_detail,
    has_prediction_read_permission,
)
from apps.scientific.app.domains.prediction.model_prediction import (
    get_active_membership_for_organization,
    get_prediction_by_id_in_db,
    get_scene_metadata_in_db,
    get_training_job_origin_in_db,
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
        membership = get_active_membership_for_organization(
            client, user_id, organization_id
        )
    except APIError as exc:
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
        prediction = get_prediction_by_id_in_db(
            client, prediction_id, organization_id
        )
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
            scene_metadata = get_scene_metadata_in_db(client, UUID(str(scene_id)))
        except (APIError, ValueError):
            scene_metadata = None

    result_payload = (
        prediction.get("result")
        if isinstance(prediction.get("result"), dict)
        else {}
    )
    training_job_row = None
    try:
        raw_training_id = result_payload.get("training_job_id")
        raw_model_version_id = prediction.get("model_version_id")
        raw_dataset_version_id = result_payload.get("dataset_version_id")
        training_job_row = get_training_job_origin_in_db(
            client,
            organization_id=organization_id,
            training_job_id=(
                UUID(str(raw_training_id)) if raw_training_id else None
            ),
            model_version_id=(
                UUID(str(raw_model_version_id))
                if raw_model_version_id
                else None
            ),
            dataset_version_id=(
                UUID(str(raw_dataset_version_id))
                if raw_dataset_version_id
                else None
            ),
        )
    except (APIError, AssertionError, AttributeError, KeyError, TypeError, ValueError):
        training_job_row = None

    return build_prediction_detail(
        prediction,
        scene_row=scene_metadata,
        training_job_row=training_job_row,
    )
