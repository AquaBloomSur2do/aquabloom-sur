from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from apps.scientific.app.core.database import supabase
from apps.scientific.app.core.dependencies import require_internal_service
from apps.scientific.app.domains.execution.domain_execution import (
    JOB_TIMEOUT_SECONDS,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    JobCreate,
    JobResponse,
    JobStatus,
)
from apps.scientific.app.domains.execution.service_execution import (
    create_execution_job_service,
    get_job_status_service,
    process_scientific_job,
)

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])

# Alias de compatibilidad para tests que parchean _process_scientific_job o JOB_TIMEOUT_SECONDS
_process_scientific_job = process_scientific_job

__all__ = ["JOB_TIMEOUT_SECONDS", "_process_scientific_job", "router"]


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
def get_job_status(job_id: UUID):
    client = _require_database()
    return get_job_status_service(client, job_id)


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    x_idempotency_key: str | None = Header(
        default=None, alias="X-Idempotency-Key", max_length=255
    ),
):
    client = _require_database()
    idempotency_key = x_idempotency_key.strip() if x_idempotency_key else None

    if idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    return create_execution_job_service(
        client,
        payload=payload,
        background_tasks=background_tasks,
        idempotency_key=idempotency_key,
    )

