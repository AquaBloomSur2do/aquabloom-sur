from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.database import supabase
from apps.api.app.domains.library.schemas_library import (
    LibraryVersionCreate,
    LibraryVersionResponse,
)
from apps.api.app.domains.library.service_library import (
    create_library_version_service,
    get_library_version_service,
)

router = APIRouter(prefix="/api/v1/library", tags=["Library"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible",
        )
    return supabase


def _extract_user_id(payload: dict) -> str | None:
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return str(UUID(str(sub)))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario inválido en el token.",
        ) from exc


@router.post(
    "/versions",
    response_model=LibraryVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_library_version(
    payload: LibraryVersionCreate,
    token_payload: Annotated[dict, Depends(verify_supabase_jwt)],
):
    """Crea una version de recurso de biblioteca con licencia y procedencia."""
    client = _require_database()
    user_id = _extract_user_id(token_payload)
    return create_library_version_service(client, payload, user_id)


@router.get(
    "/versions/{version_id}",
    response_model=LibraryVersionResponse,
    status_code=status.HTTP_200_OK,
)
def get_library_version(
    version_id: UUID,
    _token_payload: Annotated[dict, Depends(verify_supabase_jwt)],
):
    """Consulta una version de biblioteca conservando su licencia y procedencia."""
    client = _require_database()
    return get_library_version_service(client, version_id)
