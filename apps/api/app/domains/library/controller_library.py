from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.database import supabase
from apps.api.app.domains.library.schemas_library import (
    ResourceReviewRequestCreate,
    ResourceReviewRequestResponse,
)
from apps.api.app.domains.library.service_library import (
    create_resource_review_request_service,
    extract_authenticated_author_id,
    list_resource_review_requests_service,
)

router = APIRouter(prefix="/api/v1/library", tags=["Library"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )
    return supabase


@router.post(
    "/review-requests",
    response_model=ResourceReviewRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource_review_request(
    payload: ResourceReviewRequestCreate,
    current_user: Annotated[dict, Depends(verify_supabase_jwt)],
):
    """Registra una solicitud de revisión vinculada a una versión concreta."""
    db = _require_database()
    author_id = extract_authenticated_author_id(current_user)
    return create_resource_review_request_service(
        db,
        version_id=payload.version_id,
        author_id=author_id,
        notes=payload.notes,
    )


@router.get(
    "/versions/{version_id}/review-requests",
    response_model=list[ResourceReviewRequestResponse],
)
async def list_version_review_requests(
    version_id: UUID,
    current_user: Annotated[dict, Depends(verify_supabase_jwt)],
):
    """Lista las solicitudes de revisión de una versión concreta."""
    extract_authenticated_author_id(current_user)
    db = _require_database()
    return list_resource_review_requests_service(db, version_id=version_id)
