from typing import Any
from uuid import UUID

from apps.api.app.domains.library.domain_library import (
    LibraryAccessDeniedError,
    LibraryResourceNotFoundError,
    LibraryVersionNotFoundError,
    build_library_version_record,
    can_create_library_version,
    can_read_library_version,
    reconstruct_library_version_response,
)
from apps.api.app.domains.library.model_library import (
    fetch_active_organization_membership,
    fetch_library_resource_by_id,
    fetch_library_resource_version_by_id,
    insert_library_resource_version,
)
from apps.api.app.domains.library.schemas_library import LibraryVersionCreate


def create_library_version_service(
    client: Any,
    payload: LibraryVersionCreate,
    user_id: UUID,
) -> dict[str, Any]:
    resource = fetch_library_resource_by_id(client, payload.resource_id)
    if resource is None:
        raise LibraryResourceNotFoundError(
            "No se encontró el recurso de biblioteca."
        )

    owner_org_id = str(resource.get("owner_organization_id") or "")
    membership = fetch_active_organization_membership(client, owner_org_id, user_id)
    if membership is None:
        # Oculta existencia de recursos de otras organizaciones para evitar enumeración.
        raise LibraryResourceNotFoundError(
            "No se encontró el recurso de biblioteca."
        )

    if not can_create_library_version(membership.get("role")):
        raise LibraryAccessDeniedError(
            "No tienes permisos para crear versiones en este recurso de biblioteca."
        )

    record = build_library_version_record(payload, user_id)
    inserted = insert_library_resource_version(client, record)
    return reconstruct_library_version_response(inserted)


def get_library_version_service(
    client: Any,
    version_id: UUID,
    user_id: UUID,
) -> dict[str, Any]:
    row = fetch_library_resource_version_by_id(client, version_id)
    if row is None:
        raise LibraryVersionNotFoundError(
            "Versión de biblioteca no encontrada."
        )

    resource_id = UUID(str(row["resource_id"]))
    resource = fetch_library_resource_by_id(client, resource_id)
    if resource is None:
        raise LibraryVersionNotFoundError(
            "Versión de biblioteca no encontrada."
        )

    owner_org_id = str(resource.get("owner_organization_id") or "")
    membership = fetch_active_organization_membership(client, owner_org_id, user_id)
    if not can_read_library_version(
        resource_visibility=resource.get("visibility"),
        version_status=row.get("status"),
        has_active_membership=membership is not None,
    ):
        raise LibraryVersionNotFoundError(
            "Versión de biblioteca no encontrada."
        )

    return reconstruct_library_version_response(row)
