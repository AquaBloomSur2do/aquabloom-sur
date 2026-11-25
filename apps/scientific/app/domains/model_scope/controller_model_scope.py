from fastapi import APIRouter, Depends, HTTPException, status

from apps.scientific.app.core.database import supabase
from apps.scientific.app.core.dependencies import require_internal_service
from apps.scientific.app.domains.model_scope.schemas_model_scope import (
    ModelScopeCreate,
    ModelScopeResponse,
)
from apps.scientific.app.domains.model_scope.service_model_scope import (
    create_model_scope_service,
)

router = APIRouter(prefix="/api/v1/model-scopes", tags=["Scientific"])


@router.post(
    "/",
    response_model=ModelScopeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_service)],
)
def create_model_scope(payload: ModelScopeCreate):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return create_model_scope_service(supabase, payload)
