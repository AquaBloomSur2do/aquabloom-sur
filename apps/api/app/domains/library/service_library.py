from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from apps.api.app.domains.library.model_library import (
    find_resource_version_by_id,
    insert_resource_review_request,
    list_resource_review_requests_by_version,
)


def extract_authenticated_author_id(current_user: dict[str, Any]) -> UUID:
    """Extrae y valida el UUID del autor desde el token JWT autenticado."""
    raw_sub = current_user.get("sub") if isinstance(current_user, dict) else None
    if not raw_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudo identificar al usuario autenticado.",
        )
    try:
        return UUID(str(raw_sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El identificador del usuario autenticado no es válido.",
        ) from exc


def create_resource_review_request_service(
    client: Any,
    *,
    version_id: UUID,
    author_id: UUID,
    notes: str | None = None,
) -> dict[str, Any]:
    """Valida la existencia de la versión y registra la solicitud de revisión."""
    version_record = find_resource_version_by_id(client, version_id)
    if version_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión solicitada no existe.",
        )

    cleaned_notes = notes.strip() if isinstance(notes, str) and notes.strip() else None
    created = insert_resource_review_request(
        client,
        version_id=version_id,
        author_id=author_id,
        notes=cleaned_notes,
    )
    if created is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la solicitud de revisión.",
        )
    return created


def list_resource_review_requests_service(
    client: Any,
    *,
    version_id: UUID,
) -> list[dict[str, Any]]:
    """Consulta las solicitudes de revisión vinculadas a una versión."""
    version_record = find_resource_version_by_id(client, version_id)
    if version_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión solicitada no existe.",
        )
    return list_resource_review_requests_by_version(client, version_id)
