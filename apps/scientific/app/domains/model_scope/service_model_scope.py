from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from apps.scientific.app.domains.model_scope.model_model_scope import (
    insert_model_scope_in_db,
)
from apps.scientific.app.domains.model_scope.schemas_model_scope import (
    ModelScopeCreate,
)


def create_model_scope_service(client, payload: ModelScopeCreate) -> dict:
    db_payload = payload.model_dump(mode="json")
    db_payload["is_validated"] = False

    try:
        model_scope = insert_model_scope_in_db(client, db_payload)
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo registrar el alcance del modelo.",
        ) from exc

    if model_scope is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo registrar el alcance del modelo.",
        )
    return model_scope
