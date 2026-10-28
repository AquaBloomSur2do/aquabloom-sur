import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import require_internal_service
from domain.execution.schemas import JobCreate, JobResponse, JobStatus

# SOLUCIÓN AL 404: Se agregó el prefijo de la ruta base
router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])

# Diccionario temporal en memoria para pruebas locales
JOBS_DB: dict[str, dict[str, Any]] = {}


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(payload: JobCreate):
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "job_type": payload.job_type,
        "config": payload.config.model_dump(),
        "status": "pending",
        "result": None,
        "created_at": datetime.now(UTC),
    }
    JOBS_DB[job_id] = job_data

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
    dependencies=[Depends(require_internal_service)],
)
def get_job_status(job_id: str):
    if job_id not in JOBS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )
    return JOBS_DB[job_id]

