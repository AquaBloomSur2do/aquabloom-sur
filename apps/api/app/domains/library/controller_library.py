from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.database import supabase
from apps.api.app.domains.library.domain_library import (
    LibraryAccessDeniedError,
    LibraryDomainError,
    LibraryIntegrityError,
    LibraryResourceNotFoundError,
    LibraryVersionConflictError,
    LibraryVersionNotFoundError,
)
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


def _extract_user_id(payload: dict) -> UUID:
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no contiene un identificador de usuario válido.",
        )
    try:
        return UUID(sub.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario inválido en el token.",
        ) from exc


def _raise_http_from_domain_error(exc: LibraryDomainError) -> NoReturn:
    if isinstance(exc, LibraryAccessDeniedError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    if isinstance(exc, (LibraryResourceNotFoundError, LibraryVersionNotFoundError)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    if isinstance(exc, LibraryVersionConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if isinstance(exc, LibraryIntegrityError):
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=str(exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc),
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
    try:
        return create_library_version_service(client, payload, user_id)
    except LibraryDomainError as exc:
        _raise_http_from_domain_error(exc)


@router.get(
    "/versions/{version_id}",
    response_model=LibraryVersionResponse,
    status_code=status.HTTP_200_OK,
)
def get_library_version(
    version_id: UUID,
    token_payload: Annotated[dict, Depends(verify_supabase_jwt)],
):
    """Consulta una version de biblioteca conservando su licencia y procedencia."""
    client = _require_database()
    user_id = _extract_user_id(token_payload)
    try:
        return get_library_version_service(client, version_id, user_id)
    except LibraryDomainError as exc:
        _raise_http_from_domain_error(exc)
