import asyncio
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    status,
)
from postgrest.exceptions import APIError

from app.auth import verify_supabase_jwt
from app.database import supabase
from app.dependencies import require_internal_service
from domain.execution.schemas import JobCreate, JobResponse, JobStatus, TrainingConfig

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])

JOB_TIMEOUT_SECONDS = 10.0


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )
    return supabase


def _validate_training_version(client, config: TrainingConfig) -> None:
    try:
        response = (
            client.schema("dataset")
            .table("versions")
            .select("id, dataset_id, state, status")
            .eq("id", str(config.version_id))
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    rows = response.data or []
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la versión del dataset.",
        )

    version = rows[0]
    if str(version.get("dataset_id")) != str(config.dataset_id):
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


async def _process_scientific_job(job_id: str, config: dict[str, Any]) -> None:
    """Run a scientific job and persist its result or failure."""
    if supabase is None:
        return

    try:
        supabase.table("scientific_jobs").update(
            {
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", job_id).execute()

        async def _run_algorithm() -> dict[str, Any]:
            scene_id = config.get("scene_id", "")
            if scene_id == "scene_fail":
                raise RuntimeError(
                    "Excepción interna: Fallo al procesar los tensores de la escena."
                )
            if scene_id == "scene_timeout":
                await asyncio.sleep(2.0)
            else:
                await asyncio.sleep(0.1)
            return {"accuracy": 0.98, "processed_pixels": 102400}

        result = await asyncio.wait_for(
            _run_algorithm(), timeout=JOB_TIMEOUT_SECONDS
        )
        supabase.table("scientific_jobs").update(
            {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", job_id).execute()
    except TimeoutError:
        supabase.table("scientific_jobs").update(
            {
                "status": "failed",
                "error_message": (
                    "Tiempo máximo de ejecución excedido "
                    f"(Timeout de {JOB_TIMEOUT_SECONDS}s)."
                ),
                "completed_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", job_id).execute()
    except Exception as exc:  # noqa: BLE001
        supabase.table("scientific_jobs").update(
            {
                "status": "failed",
                "error_message": str(exc),
                "completed_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", job_id).execute()


def _find_job(
    client, *, job_id: str | None = None, idempotency_key: str | None = None
) -> dict[str, Any] | None:
    query = client.table("scientific_jobs").select("*")
    if job_id is not None:
        query = query.eq("id", job_id)
    elif idempotency_key is not None:
        query = query.eq("idempotency_key", idempotency_key)
    else:
        raise ValueError("Se requiere job_id o idempotency_key.")

    result = query.limit(1).execute()
    return result.data[0] if getattr(result, "data", None) else None


def _matches_request(
    job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return (
        job.get("job_type") == payload.job_type
        and job.get("organization_id") == str(payload.organization_id)
        and job.get("config") == config
    )


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
    description=(
        "Devuelve el estado de un trabajo solo si el usuario autenticado "
        "pertenece activamente a la organización propietaria."
    ),
)
def get_job_status(
    job_id: UUID,
    payload: Annotated[dict, Depends(verify_supabase_jwt)],
) -> JobStatus:
    client = _require_database()

    try:
        response = (
            client.table("scientific_jobs")
            .select(
                "id, organization_id, job_type, status, config, result, "
                "dataset_version_id, model_version_id, requested_by, "
                "error_message, created_at, started_at, completed_at, updated_at"
            )
            .eq("id", str(job_id))
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    rows = getattr(response, "data", None) if response else None
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )

    job = rows[0]
    organization_id = job.get("organization_id")
    if organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )

    try:
        user_id = str(UUID(str(payload.get("sub"))))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin un identificador de usuario válido.",
        ) from exc

    try:
        membership = (
            client.table("memberships")
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
) -> JobResponse:
    client = _require_database()
    idempotency_key = x_idempotency_key.strip() if x_idempotency_key else None
    if idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    if payload.job_type == "training":
        _validate_training_version(client, payload.config)

    config = payload.config.model_dump(mode="json")
    if idempotency_key is not None:
        existing_job = _find_job(client, idempotency_key=idempotency_key)
        if existing_job is not None:
            if _matches_request(existing_job, payload, config):
                return _job_response(existing_job)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La clave de idempotencia ya fue utilizada "
                    "con un contenido diferente."
                ),
            )

    db_payload = {
        "job_type": payload.job_type,
        "organization_id": str(payload.organization_id),
        "config": config,
        "status": "queued",
    }
    if idempotency_key is not None:
        db_payload["idempotency_key"] = idempotency_key

    try:
        insert_result = client.table("scientific_jobs").insert(db_payload).execute()
    except APIError as exc:
        if exc.code == "23505" and idempotency_key is not None:
            existing_job = _find_job(client, idempotency_key=idempotency_key)
            if existing_job is not None:
                if _matches_request(existing_job, payload, config):
                    return _job_response(existing_job)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "La clave de idempotencia ya fue utilizada "
                        "con un contenido diferente."
                    ),
                ) from exc
        _raise_database_error(exc)
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    if not getattr(insert_result, "data", None):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo persistir el trabajo.",
        )

    inserted_job = insert_result.data[0]
    background_tasks.add_task(
        _process_scientific_job, str(inserted_job["id"]), config
    )
    return _job_response(inserted_job)


def _raise_database_error(exc: Exception) -> None:
    error_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la organización asociada al trabajo.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo completar la operación del trabajo.",
    ) from exc
