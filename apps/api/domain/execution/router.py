from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from postgrest.exceptions import APIError

from app.database import supabase
from app.dependencies import require_internal_service
from domain.execution.schemas import JobCreate, JobResponse, JobStatus

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


def _find_job(
    *, job_id: str | None = None, idempotency_key: str | None = None
) -> dict[str, Any] | None:
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    query = supabase.table("scientific_jobs").select("*")
    if job_id is not None:
        query = query.eq("id", job_id)
    elif idempotency_key is not None:
        query = query.eq("idempotency_key", idempotency_key)
    else:
        raise ValueError("Se requiere job_id o idempotency_key.")

    result = query.limit(1).execute()
    return result.data[0] if result.data else None


def _matches_request(
    job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return job.get("job_type") == payload.job_type and job.get("config") == config


def _job_response(job: dict[str, Any]) -> dict[str, Any]:
    job_id = UUID(str(job["id"]))
    return {
        "job_id": job_id,
        "status": job["status"],
        "status_url": f"/api/v1/executions/{job_id}",
    }


@router.get(
    "/{job_id}",
    response_model=JobStatus,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_internal_service)],
)
def get_job_status(job_id: UUID):
    job = _find_job(job_id=str(job_id))
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )

    return {
        "job_id": job["id"],
        "status": job["status"],
        "result": job.get("result"),
        "created_at": job["created_at"],
    }


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(
    payload: JobCreate,
    x_idempotency_key: str | None = Header(
        default=None, alias="X-Idempotency-Key", max_length=255
    ),
):
    idempotency_key = x_idempotency_key.strip() if x_idempotency_key else None
    if idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    config = payload.config.model_dump()

    if idempotency_key is not None:
        existing_job = _find_job(idempotency_key=idempotency_key)
        if existing_job is not None:
            if _matches_request(existing_job, payload, config):
                return _job_response(existing_job)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La clave de idempotencia ya fue utilizada con un contenido diferente.",
            )

    db_payload = {
        "job_type": payload.job_type,
        "config": config,
        "status": "pending",
    }
    if idempotency_key is not None:
        db_payload["idempotency_key"] = idempotency_key

    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    try:
        insert_result = supabase.table("scientific_jobs").insert(db_payload).execute()
    except APIError as exc:
        if exc.code == "23505" and idempotency_key is not None:
            existing_job = _find_job(idempotency_key=idempotency_key)
            if existing_job is not None:
                if _matches_request(existing_job, payload, config):
                    return _job_response(existing_job)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La clave de idempotencia ya fue utilizada con un contenido diferente.",
                ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo persistir el trabajo.",
        ) from exc

    if not insert_result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo persistir el trabajo.",
        )

    return _job_response(insert_result.data[0])
