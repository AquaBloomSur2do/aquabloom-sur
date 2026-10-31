from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import supabase
from app.dependencies import require_internal_service
from domain.execution.schemas import (
    JobCreate,
    JobResponse,
    JobStatus,
    TrainingConfig,
)

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


def _validate_training_version(client, config: TrainingConfig) -> None:
    rows = (
        client.schema("dataset")
        .table("versions")
        .select("id, dataset_id, state, status")
        .eq("id", str(config.version_id))
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la versión del dataset.",
        )

    version = rows[0]
    if str(version.get("dataset_id")) != config.dataset_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La versión no pertenece al dataset indicado.",
        )

    version_state = version.get("state") or version.get("status")
    if str(version_state).upper() != "PUBLISHED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden entrenar versiones publicadas.",
        )

@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(payload: JobCreate):
    client = _require_database()
    if payload.job_type == "training":
        _validate_training_version(client, payload.config)

    response = (
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
    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el trabajo científico.",
        )

    job = rows[0]
    job_id = str(job["id"])

    return {
        "job_id": job_id,
        "status": job["status"],
        "status_url": f"/api/v1/executions/{job_id}",
        "message": "Job created and awaiting background processing",
    }


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
def get_job_status(job_id: UUID):
    client = _require_database()
    response = (
        client.table("scientific_jobs")
        .select("id, status, result, created_at")
        .eq("id", str(job_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )
    job = rows[0]
    return {
        "job_id": job["id"],
        "status": job["status"],
        "result": job.get("result"),
        "created_at": job["created_at"],
    }
