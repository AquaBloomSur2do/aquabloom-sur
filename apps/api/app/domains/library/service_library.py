from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from apps.api.app.domains.library.domain_library import (
    build_library_version_record,
)
from apps.api.app.domains.library.model_library import (
    fetch_library_version_by_id,
    insert_library_version,
)
from apps.api.app.domains.library.schemas_library import (
    LibraryAttribution,
    LibraryVersionCreate,
)


def _normalize_persisted_version(row: dict[str, Any]) -> dict[str, Any]:
    raw_attribution = row.get("attribution")
    if not isinstance(raw_attribution, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La versión persistida no conserva su atribución.",
        )
    validated_attribution = LibraryAttribution.model_validate(raw_attribution)
    return {
        "id": row["id"],
        "resource_id": row["resource_id"],
        "status": row.get("status", "draft"),
        "attribution": validated_attribution.model_dump(mode="json"),
        "created_by": row.get("created_by"),
        "created_at": row["created_at"],
    }


def create_library_version_service(
    client: Any,
    payload: LibraryVersionCreate,
    user_id: str | None,
) -> dict[str, Any]:
    try:
        record = build_library_version_record(payload, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    inserted = insert_library_version(client, record)
    return _normalize_persisted_version(inserted)


def get_library_version_service(
    client: Any,
    version_id: UUID,
) -> dict[str, Any]:
    row = fetch_library_version_by_id(client, version_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Versión de biblioteca no encontrada.",
        )
    return _normalize_persisted_version(row)
