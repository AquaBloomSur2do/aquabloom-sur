from typing import Any, NoReturn
from uuid import UUID

from apps.api.app.domains.library.domain_library import (
    LibraryIntegrityError,
    LibraryPersistenceError,
    LibraryResourceNotFoundError,
    LibraryVersionConflictError,
    LibraryVersionNotFoundError,
)

try:
    from postgrest.exceptions import APIError
except (ImportError, ModuleNotFoundError):
    try:
        from supabase.lib.client_options import APIError
    except (ImportError, ModuleNotFoundError):

        class APIError(Exception):
            code: str = "500"

            def __init__(self, error: object = None):
                super().__init__(error)
                if isinstance(error, dict):
                    self.code = str(error.get("code", self.code))


def translate_library_database_error(exc: APIError) -> NoReturn:
    error_code = str(getattr(exc, "code", ""))
    if error_code == "23505":
        raise LibraryVersionConflictError(
            "Ya existe esa versión SemVer para el recurso de biblioteca indicado."
        ) from exc
    if error_code == "23503":
        raise LibraryResourceNotFoundError(
            "No existe el recurso o usuario asociado a la versión."
        ) from exc
    if error_code == "23514":
        raise LibraryIntegrityError(
            "La atribución de la versión incumple las reglas de integridad."
        ) from exc
    if error_code == "PGRST116":
        raise LibraryVersionNotFoundError(
            "La versión de biblioteca solicitada no existe."
        ) from exc
    raise LibraryPersistenceError(
        "No se pudo completar la operación en el dominio de biblioteca."
    ) from exc


def fetch_library_resource_by_id(
    client: Any, resource_id: UUID
) -> dict[str, Any] | None:
    try:
        response = (
            client.schema("library")
            .table("resources")
            .select("id, owner_organization_id, visibility")
            .eq("id", str(resource_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        translate_library_database_error(exc)

    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None


def fetch_active_organization_membership(
    client: Any, organization_id: str, user_id: UUID
) -> dict[str, Any] | None:
    try:
        response = (
            client.table("memberships")
            .select("id, organization_id, user_id, role, status")
            .eq("organization_id", str(organization_id))
            .eq("user_id", str(user_id))
            .eq("status", "active")
            .limit(1)
            .execute()
        )
    except APIError as exc:
        translate_library_database_error(exc)

    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None


def insert_library_resource_version(
    client: Any, record: dict[str, Any]
) -> dict[str, Any]:
    try:
        response = (
            client.schema("library")
            .table("resource_versions")
            .insert(record)
            .execute()
        )
    except APIError as exc:
        translate_library_database_error(exc)

    rows = getattr(response, "data", None) or []
    if not rows:
        raise LibraryPersistenceError(
            "La base de datos no devolvió la versión de biblioteca creada."
        )
    return rows[0]


def fetch_library_resource_version_by_id(
    client: Any, version_id: UUID
) -> dict[str, Any] | None:
    try:
        response = (
            client.schema("library")
            .table("resource_versions")
            .select(
                "id, resource_id, version, status, author, license, source, created_by, created_at"
            )
            .eq("id", str(version_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        translate_library_database_error(exc)

    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None
