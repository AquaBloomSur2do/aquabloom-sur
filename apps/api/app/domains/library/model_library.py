from typing import Any, NoReturn
from uuid import UUID

from fastapi import HTTPException, status

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


def raise_library_database_error(exc: APIError) -> NoReturn:
    error_code = str(getattr(exc, "code", ""))
    if error_code == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La versión de biblioteca entra en conflicto con un registro existente.",
        ) from exc
    if error_code == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe el recurso o usuario asociado a la versión.",
        ) from exc
    if error_code == "23514":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La atribución de la versión incumple las reglas de integridad.",
        ) from exc
    if error_code == "PGRST116":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La versión de biblioteca solicitada no existe.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo completar la operación en el dominio de biblioteca.",
    ) from exc


def insert_library_version(client: Any, record: dict[str, Any]) -> dict[str, Any]:
    try:
        response = (
            client.schema("library")
            .table("versions")
            .insert(record)
            .execute()
        )
    except APIError as exc:
        raise_library_database_error(exc)

    rows = getattr(response, "data", None) or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La base de datos no devolvió la versión de biblioteca creada.",
        )
    return rows[0]


def fetch_library_version_by_id(
    client: Any, version_id: UUID
) -> dict[str, Any] | None:
    try:
        response = (
            client.schema("library")
            .table("versions")
            .select("id, resource_id, status, attribution, created_by, created_at")
            .eq("id", str(version_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        raise_library_database_error(exc)

    rows = getattr(response, "data", None) or []
    return rows[0] if rows else None
