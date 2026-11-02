from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import verify_supabase_jwt
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


@router.post(
    "/",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_service)],
)
def create_execution_job(payload: JobCreate) -> JobResponse:
    client = _require_database()
    if payload.job_type == "training":
        _validate_training_version(client, payload.config)

    try:
        response = (
            client.table("scientific_jobs")
            .insert(
                {
                    "job_type": payload.job_type,
                    "organization_id": str(payload.organization_id),
                    "config": payload.config.model_dump(mode="json"),
                    "status": "queued",
                }
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    rows = getattr(response, "data", None) if response else None
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el trabajo.",
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
