from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import verify_supabase_jwt
from app.database import supabase
from app.dependencies import require_internal_service
from domain.execution.schemas import JobCreate, JobResponse, JobStatus

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(payload: JobCreate) -> JobResponse:
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    try:
        response = (
            supabase.table("scientific_jobs")
            .insert(
                {
                    "job_type": payload.job_type,
                    "organization_id": str(payload.organization_id),
                    "config": payload.config.model_dump(mode="json"),
                    "status": "pending",
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    if not getattr(response, "data", None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el trabajo.",
        )

    job_id = str(response.data[0]["id"])
    return {
        "job_id": job_id,
        "status": "pending",
        "status_url": f"/api/v1/executions/{job_id}",
        "message": "Job accepted and processing in background",
    }

@router.get(
    "/{job_id}",
    response_model=JobStatus,
    status_code=status.HTTP_200_OK,
    description=(
        "Devuelve el estado de un trabajo solo si el usuario autenticado "
        "pertenece activamente a la organización propietaria."
    ),
)
def get_job_status(
    job_id: UUID,
    payload: Annotated[dict, Depends(verify_supabase_jwt)],
) -> JobStatus:
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    try:
        response = (
            supabase.table("scientific_jobs")
            .select("id, organization_id, status, result, created_at")
            .eq("id", str(job_id))
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    if not getattr(response, "data", None):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )

    job = response.data[0]
    organization_id = job.get("organization_id")
    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )

    user_id = payload.get("sub")
    try:
        user_id = str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin un identificador de usuario válido.",
        ) from exc

    try:
        membership = (
            supabase.table("memberships")
            .select("id")
            .eq("user_id", user_id)
            .eq("organization_id", str(organization_id))
            .eq("status", "active")
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    if not getattr(membership, "data", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No perteneces a la organización propietaria del trabajo.",
        )

    return {
        "job_id": job["id"],
        "status": job["status"],
        "result": job.get("result"),
        "created_at": job["created_at"],
    }


def _raise_database_error(exc: Exception) -> None:
    error_code = getattr(exc, "code", None)
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la organización asociada al trabajo.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo completar la operación del trabajo.",
    ) from exc
