from typing import Any
from uuid import UUID

INITIAL_REVIEW_REQUEST_STATUS = "submitted"


def find_resource_version_by_id(
    client: Any,
    version_id: UUID | str,
) -> dict[str, Any] | None:
    """Consulta si existe la versión concreta en dataset.versions."""
    response = (
        client.schema("dataset")
        .table("versions")
        .select("id")
        .eq("id", str(version_id))
        .limit(1)
        .execute()
    )
    data = getattr(response, "data", None) or []
    return data[0] if data else None


def insert_resource_review_request(
    client: Any,
    *,
    version_id: UUID | str,
    author_id: UUID | str,
    notes: str | None = None,
) -> dict[str, Any] | None:
    """Inserta una solicitud de revisión con estado inicial controlado por el servidor."""
    payload: dict[str, Any] = {
        "version_id": str(version_id),
        "author_id": str(author_id),
        "status": INITIAL_REVIEW_REQUEST_STATUS,
    }
    if notes is not None:
        payload["notes"] = notes

    response = client.table("resource_review_requests").insert(payload).execute()
    data = getattr(response, "data", None) or []
    return data[0] if data else None


def get_resource_review_request_by_id(
    client: Any,
    request_id: UUID | str,
) -> dict[str, Any] | None:
    """Obtiene una solicitud de revisión por su identificador."""
    response = (
        client.table("resource_review_requests")
        .select("*")
        .eq("id", str(request_id))
        .limit(1)
        .execute()
    )
    data = getattr(response, "data", None) or []
    return data[0] if data else None


def list_resource_review_requests_by_version(
    client: Any,
    version_id: UUID | str,
) -> list[dict[str, Any]]:
    """Lista las solicitudes de revisión asociadas a una versión concreta."""
    response = (
        client.table("resource_review_requests")
        .select("*")
        .eq("version_id", str(version_id))
        .execute()
    )
    return getattr(response, "data", None) or []
