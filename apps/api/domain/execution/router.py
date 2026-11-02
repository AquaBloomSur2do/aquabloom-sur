import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import supabase
from app.dependencies import require_internal_service
from domain.execution.schemas import JobCreate, JobResponse, JobStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(payload: JobCreate):
    client = _require_database()
    try:
        database_response = (
            client.table("scientific_jobs")
            .insert(
                {
                    "job_type": payload.job_type,
                    "config": payload.config.model_dump(mode="json"),
                    "status": "pending",
                }
            )
            .execute()
        )
    except Exception as exc:
        logger.exception("No se pudo registrar el trabajo científico.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo registrar el trabajo científico.",
        ) from exc

    if not database_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se devolvieron los datos del trabajo registrado.",
        )

    job = database_response.data[0]
    job_id = str(job["id"])

    return {
        "job_id": job_id,
        "status": job["status"],
        "status_url": f"/api/v1/executions/{job_id}",
        "message": "Job accepted and processing in background",
    }


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
def get_job_status(job_id: UUID):
    client = _require_database()
    try:
        database_response = (
            client.table("scientific_jobs")
            .select("id, status, result, created_at")
            .eq("id", str(job_id))
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.exception("No se pudo consultar el trabajo %s.", job_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo consultar el estado del trabajo.",
        ) from exc

    if not database_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )
    job = database_response.data[0]
    return {
        "job_id": job["id"],
        "status": job["status"],
        "result": job.get("result"),
        "created_at": job["created_at"],
    }
