from typing import Any
from uuid import UUID

from apps.api.app.domains.library.schemas_library import (
    LibraryAttribution,
    LibraryVersionCreate,
)

ALLOWED_VERSION_CREATOR_ROLES = frozenset({"author", "org_admin"})


class LibraryDomainError(Exception):
    """Error base del dominio de biblioteca independiente del transporte HTTP."""


class LibraryResourceNotFoundError(LibraryDomainError):
    """El recurso padre no existe o no es visible para la organización del usuario."""


class LibraryVersionNotFoundError(LibraryDomainError):
    """La versión solicitada no existe o el usuario no tiene acceso a ella."""


class LibraryAccessDeniedError(LibraryDomainError):
    """El usuario pertenece a la organización pero carece de rol autorizado."""


class LibraryVersionConflictError(LibraryDomainError):
    """Ya existe una versión con el mismo identificador SemVer para el recurso."""


class LibraryIntegrityError(LibraryDomainError):
    """Los datos incumplen las restricciones de integridad del dominio."""


class LibraryPersistenceError(LibraryDomainError):
    """Error inesperado al persistir o recuperar datos de biblioteca."""


def can_create_library_version(role: str | None) -> bool:
    """Verifica si el rol organizacional puede crear borradores de versión (S3-05)."""
    if not role:
        return False
    return role.strip().lower() in ALLOWED_VERSION_CREATOR_ROLES


def can_read_library_version(
    *,
    resource_visibility: str | None,
    version_status: str | None,
    has_active_membership: bool,
) -> bool:
    """Determina si el usuario autenticado puede consultar una versión de biblioteca."""
    if has_active_membership:
        return True
    return (
        str(resource_visibility or "").strip().lower() == "public"
        and str(version_status or "").strip().lower() == "published"
    )


def build_library_version_record(
    payload: LibraryVersionCreate,
    user_id: UUID,
) -> dict[str, Any]:
    """Mapea el payload de creación a las columnas oficiales de library.resource_versions (S3-08)."""
    attribution_data = payload.attribution.model_dump(mode="json")
    return {
        "resource_id": str(payload.resource_id),
        "version": attribution_data["version"],
        "status": "draft",
        "author": attribution_data["author"],
        "license": attribution_data["license"],
        "source": attribution_data["source"],
        "created_by": str(user_id),
    }


def reconstruct_library_version_response(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstruye la respuesta HTTP desde las columnas relacionales de library.resource_versions."""
    try:
        validated_attribution = LibraryAttribution.model_validate(
            {
                "author": row.get("author"),
                "license": row.get("license"),
                "version": row.get("version"),
                "source": row.get("source"),
            }
        )
    except ValueError as exc:
        raise LibraryIntegrityError(
            "La versión persistida no conserva una atribución válida."
        ) from exc

    return {
        "id": row["id"],
        "resource_id": row["resource_id"],
        "status": row.get("status", "draft"),
        "attribution": validated_attribution.model_dump(mode="json"),
        "created_by": row.get("created_by"),
        "created_at": row["created_at"],
    }
