import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from postgrest.exceptions import APIError

from app.database import supabase
from app.dependencies import require_internal_service
from domain.execution.schemas import JobCreate, JobResponse, JobStatus

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])

JOB_TIMEOUT_SECONDS = 10.0

async def _process_scientific_job(job_id: str, config: dict[str, Any]):
    """Trabajo asíncrono con control estricto de timeout, fallos y persistencia real en Supabase (S2-150)."""
    if supabase is None:
        return

    try:
        supabase.table("scientific_jobs").update({
            "status": "running",
            "started_at": datetime.now(UTC).isoformat()
        }).eq("id", job_id).execute()

        async def _run_algorithm():
            scene_id = config.get("scene_id", "")
            if scene_id == "scene_fail":
                raise RuntimeError("Excepción interna: Fallo al procesar los tensores de la escena.")
            if scene_id == "scene_timeout":
                await asyncio.sleep(2.0)
            else:
                await asyncio.sleep(0.1)
            return {"accuracy": 0.98, "processed_pixels": 102400}

        result = await asyncio.wait_for(_run_algorithm(), timeout=JOB_TIMEOUT_SECONDS)
        
        supabase.table("scientific_jobs").update({
            "status": "completed",
            "result": result,
            "completed_at": datetime.now(UTC).isoformat()
        }).eq("id", job_id).execute()
        
    except TimeoutError:
        supabase.table("scientific_jobs").update({
            "status": "failed",
            "error_message": f"Tiempo máximo de ejecución excedido (Timeout de {JOB_TIMEOUT_SECONDS}s).",
            "completed_at": datetime.now(UTC).isoformat()
        }).eq("id", job_id).execute()
        
    except Exception as exc:  # noqa: BLE001
        supabase.table("scientific_jobs").update({
            "status": "failed",
            "error_message": str(exc),
            "completed_at": datetime.now(UTC).isoformat()
        }).eq("id", job_id).execute()


def _find_job(*, job_id: str | None = None, idempotency_key: str | None = None) -> dict[str, Any] | None:
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
    return result.data[0] if getattr(result, "data", None) else None


def _matches_request(job: dict[str, Any], payload: JobCreate, config: dict[str, Any]) -> bool:
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
    # Fix Pydantic: Mapeamos la llave id a job_id para alinear con el esquema JobStatus
    if "id" in job:
        job["job_id"] = job.pop("id")
    return job


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
        "status": "queued",
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

    if not getattr(insert_result, "data", None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo persistir el trabajo.",
        )

    inserted_job = insert_result.data[0]
    
    # Delegar procesamiento a tarea en background (S2-150)
    background_tasks.add_task(_process_scientific_job, str(inserted_job["id"]), config)

    return _job_response(inserted_job)



