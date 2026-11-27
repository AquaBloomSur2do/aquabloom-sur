from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status

from apps.api.app.domains.reports.schemas_reports import (
    ResourceReportCreate,
    ResourceReportResolution,
)

MODERATOR_ROLES = {"admin", "administrador", "supervisor"}


def _is_moderator(client, user_id: UUID) -> bool:
    response = (
        client.table("memberships")
        .select("role")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .in_("role", list(MODERATOR_ROLES))
        .execute()
    )
    return bool(response.data)


def _requester_id(requester: dict) -> UUID:
    try:
        return UUID(str(requester["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin un identificador de usuario válido.",
        ) from exc


def _get_report(client, report_id: UUID) -> dict:
    response = (
        client.table("resource_reports")
        .select("*")
        .eq("id", str(report_id))
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El reporte no existe.",
        )
    return response.data[0]


def create_resource_report(
    client, payload: ResourceReportCreate, reporter_id: UUID
) -> dict:
    resource_table = {"lake": "lakes", "station": "stations"}[payload.resource_type]
    resource_response = (
        client.table(resource_table)
        .select("id")
        .eq("id", str(payload.resource_id))
        .limit(1)
        .execute()
    )
    if not resource_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El recurso reportado no existe.",
        )

    report_data = {
        "resource_type": payload.resource_type,
        "resource_id": str(payload.resource_id),
        "reported_by": str(reporter_id),
        "reason": payload.reason,
        "details": payload.details,
        "status": "open",
    }
    response = client.table("resource_reports").insert(report_data).execute()
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se devolvieron datos al guardar el reporte.",
        )
    return response.data[0]


def list_resource_reports(client, requester: dict) -> list[dict]:
    requester_id = _requester_id(requester)
    query = client.table("resource_reports").select("*")
    if not _is_moderator(client, requester_id):
        query = query.eq("reported_by", str(requester_id))
    response = query.execute()
    return response.data or []


def get_resource_report(client, report_id: UUID, requester: dict) -> dict:
    report = _get_report(client, report_id)
    requester_id = _requester_id(requester)

    if str(requester_id) != str(report["reported_by"]) and not _is_moderator(
        client, requester_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para consultar este reporte.",
        )
    return report


def resolve_resource_report(
    client,
    report_id: UUID,
    resolution: ResourceReportResolution,
    moderator: dict,
) -> dict:
    moderator_id = _requester_id(moderator)

    if not _is_moderator(client, moderator_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo un moderador puede resolver reportes.",
        )

    report = _get_report(client, report_id)
    if report["status"] != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El reporte ya fue resuelto.",
        )

    resolved_at = datetime.now(UTC).isoformat()
    response = (
        client.table("resource_reports")
        .update(
            {
                "status": "resolved",
                "resolution_reason": resolution.resolution_reason,
                "resolved_by": str(moderator_id),
                "resolved_at": resolved_at,
                "updated_at": resolved_at,
            }
        )
        .eq("id", str(report_id))
        .eq("status", "open")
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El reporte ya no está abierto.",
        )
    return response.data[0]
