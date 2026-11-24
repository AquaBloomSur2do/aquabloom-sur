from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from apps.scientific.app.domains.prediction.model_prediction import (
    insert_prediction_in_db,
)
from apps.scientific.app.domains.prediction.schemas_prediction import (
    PredictionCreate,
)


def create_prediction_service(client, payload: PredictionCreate) -> dict:
    db_payload = payload.model_dump(mode="json")

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
