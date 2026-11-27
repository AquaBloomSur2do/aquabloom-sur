from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.database import supabase
from apps.api.app.domains.reports.schemas_reports import (
    ResourceReportCreate,
    ResourceReportResolution,
    ResourceReportResponse,
)
from apps.api.app.domains.reports.service_reports import (
    create_resource_report,
    get_resource_report,
    resolve_resource_report,
)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


def _get_user_id(payload: dict) -> UUID:
    try:
        return UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin un identificador de usuario válido.",
        ) from exc


@router.post(
    "",
    response_model=ResourceReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    report: ResourceReportCreate,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    return create_resource_report(_require_database(), report, _get_user_id(payload))


@router.get("/{report_id}", response_model=ResourceReportResponse)
def read_report(
    report_id: UUID,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    return get_resource_report(_require_database(), report_id, payload)


@router.patch("/{report_id}/resolve", response_model=ResourceReportResponse)
def resolve_report(
    report_id: UUID,
    resolution: ResourceReportResolution,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    return resolve_resource_report(
        _require_database(), report_id, resolution, payload
    )
