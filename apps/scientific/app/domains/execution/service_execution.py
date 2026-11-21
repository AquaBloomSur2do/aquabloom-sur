import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from apps.scientific.app.core.database import supabase
from apps.scientific.app.domains.execution.domain_execution import (
    JOB_TIMEOUT_SECONDS,
    build_job_accepted_response,
    job_matches_request,
    run_scientific_algorithm,
)
from apps.scientific.app.domains.execution.model_execution import (
    find_scientific_job_in_db,
    get_dataset_version_for_training,
    has_active_organization_membership,
    insert_scientific_job_in_db,
    update_scientific_job_in_db,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    JobCreate,
    TrainingConfig,
)
from fastapi import BackgroundTasks, HTTPException, status
from postgrest.exceptions import APIError


def validate_training_version_service(client, config: TrainingConfig) -> None:
    version = get_dataset_version_for_training(client, config.version_id)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró la versión del dataset.",
        )

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


async def process_scientific_job(job_id: str, config: dict[str, Any]) -> None:
    """Trabajo asíncrono con control estricto de timeout, fallos y persistencia (S2-150)."""
    if supabase is None:
        return

    try:
        update_scientific_job_in_db(
            supabase,
            job_id,
            {
                "status": "running",
                "started_at": datetime.now(UTC).isoformat(),
            },
        )

        result = await asyncio.wait_for(
            run_scientific_algorithm(config), timeout=JOB_TIMEOUT_SECONDS
        )

        update_scientific_job_in_db(
            supabase,
            job_id,
            {
                "status": "completed",
                "result": result,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )

    except TimeoutError:
        update_scientific_job_in_db(
            supabase,
            job_id,
            {
                "status": "failed",
                "error_message": f"Tiempo máximo de ejecución excedido (Timeout de {JOB_TIMEOUT_SECONDS}s).",
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )

    except Exception as exc:  # noqa: BLE001
        update_scientific_job_in_db(
            supabase,
            job_id,
            {
                "status": "failed",
                "error_message": str(exc),
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )


def validate_job_organization_service(
    client, user_id: UUID, organization_id: UUID
) -> None:
    if not has_active_organization_membership(client, user_id, organization_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )


def get_job_status_service(
    client, job_id: UUID, user_id: UUID, organization_id: UUID
) -> dict[str, Any]:
    validate_job_organization_service(client, user_id, organization_id)
    job = find_scientific_job_in_db(
        client, job_id=str(job_id), organization_id=organization_id
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )
    if "id" in job:
        job["job_id"] = job.pop("id")
    return job


def create_execution_job_service(
    client,
    *,
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None,
    user_id: UUID,
    organization_id: UUID,
) -> dict[str, Any]:
    validate_job_organization_service(client, user_id, organization_id)
    config = payload.config.model_dump(mode="json")

    if idempotency_key is not None:
        existing_job = find_scientific_job_in_db(
            client,
            idempotency_key=idempotency_key,
            organization_id=organization_id,
        )
        if existing_job is not None:
            if job_matches_request(existing_job, payload, config):
                return build_job_accepted_response(existing_job)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La clave de idempotencia ya fue utilizada con un contenido diferente.",
            )

    if payload.job_type == "training":
        validate_training_version_service(client, payload.config)

    db_payload: dict[str, Any] = {
        "job_type": payload.job_type,
        "config": config,
        "status": "queued",
        "organization_id": str(organization_id),
        "requested_by": str(user_id),
    }
    if idempotency_key is not None:
        db_payload["idempotency_key"] = idempotency_key

    try:
        inserted_job = insert_scientific_job_in_db(client, db_payload)
    except APIError as exc:
        if getattr(exc, "code", None) == "23505" and idempotency_key is not None:
            existing_job = find_scientific_job_in_db(
                client,
                idempotency_key=idempotency_key,
                organization_id=organization_id,
            )
            if existing_job is not None:
                if job_matches_request(existing_job, payload, config):
                    return build_job_accepted_response(existing_job)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La clave de idempotencia ya fue utilizada con un contenido diferente.",
                ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo persistir el trabajo.",
        ) from exc

    if not inserted_job:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo persistir el trabajo.",
        )

    background_tasks.add_task(
        process_scientific_job, str(inserted_job["id"]), config
    )
    return build_job_accepted_response(inserted_job)
