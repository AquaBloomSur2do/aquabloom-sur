import asyncio
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from postgrest.exceptions import APIError

from apps.scientific.app.core.config import settings
from apps.scientific.app.core.database import supabase
from apps.scientific.app.domains.execution.domain_execution import (
    JobLimitExceededError,
    build_completed_update_payload,
    build_failure_update_payload,
    build_job_accepted_response,
    build_running_update_payload,
    build_timeout_error_message,
    calculate_baseline,
    format_exception_error_message,
    format_limit_exceeded_error_message,
    job_matches_request,
    parse_training_csv,
    resolve_job_timeout,
    split_training_validation,
)
from apps.scientific.app.domains.execution.model_execution import (
    fetch_training_file,
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

logger = logging.getLogger(__name__)
JOB_TIMEOUT_SECONDS = settings.job_timeout_seconds


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_optional_uuid_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


def _resolve_training_origin_for_estimation(
    client,
    *,
    organization_id: str | None,
    training_job_id: str | None,
    model_version_id: str | None,
) -> dict[str, Any] | None:
    """Consulta el trabajo de entrenamiento de origen si está disponible en BD."""
    if client is None or not organization_id:
        return None
    try:
        query = (
            client.table("scientific_jobs")
            .select(
                "id, status, config, result, dataset_version_id, model_version_id"
            )
            .eq("organization_id", str(organization_id))
            .eq("job_type", "training")
        )
        if training_job_id:
            query = query.eq("id", str(training_job_id))
        elif model_version_id:
            query = query.eq("model_version_id", str(model_version_id))
        else:
            return None

        rows = getattr(query.limit(1).execute(), "data", None) or []
        return rows[0] if rows else None
    except (APIError, AssertionError, AttributeError, KeyError, TypeError, ValueError):
        return None


def _persist_job_failure(job_id: str, error_message: str) -> None:
    """Persiste el estado fallido del trabajo sin propagar fallos secundarios de BD."""
    if supabase is None:
        return
    try:
        update_scientific_job_in_db(
            supabase,
            job_id,
            build_failure_update_payload(error_message, _utc_now_iso()),
        )
    except Exception:
        logger.exception(
            "No se pudo persistir el estado fallido para el trabajo %s.", job_id
        )


async def run_scientific_algorithm(
    client, job_type: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Orquesta la carga de datos y el procesamiento del trabajo científico."""
    if job_type == "estimation":
        await asyncio.sleep(1)
        model_id = config.get("model_id")
        model_version_id = config.get("model_version_id") or _parse_optional_uuid_str(
            model_id
        )
        model_name = config.get("model_name")
        training_job_id = config.get("training_job_id")

        origin_job = await asyncio.to_thread(
            _resolve_training_origin_for_estimation,
            client,
            organization_id=config.get("organization_id"),
            training_job_id=str(training_job_id) if training_job_id else None,
            model_version_id=str(model_version_id) if model_version_id else None,
        )
        if not origin_job:
            raise ValueError(
                "No se encontró el trabajo de entrenamiento de origen del modelo."
            )
        if str(origin_job.get("status", "")).lower() != "completed":
            raise ValueError(
                "El trabajo de entrenamiento de origen aún no está completado."
            )

        origin_config = origin_job.get("config") or {}
        origin_result = origin_job.get("result") or {}
        training_job_id = str(origin_job.get("id"))
        dataset_id = (
            origin_config.get("dataset_id")
            or origin_result.get("dataset_id")
        )
        dataset_version_id = (
            origin_job.get("dataset_version_id")
            or origin_config.get("version_id")
            or origin_result.get("dataset_version_id")
        )
        model_version_id = (
            origin_job.get("model_version_id")
            or origin_result.get("model_version_id")
            or model_version_id
        )
        model_name = model_name or origin_result.get("model")
        if not dataset_id or not dataset_version_id:
            raise ValueError(
                "El entrenamiento de origen no informa el dataset y su versión."
            )

        return {
            "status": "completed",
            "scene_id": config.get("scene_id"),
            "model_id": str(model_id) if model_id is not None else None,
            "model_name": str(model_name) if model_name is not None else None,
            "model_version_id": (
                str(model_version_id) if model_version_id is not None else None
            ),
            "training_job_id": (
                str(training_job_id) if training_job_id is not None else None
            ),
            "dataset_id": str(dataset_id) if dataset_id is not None else None,
            "dataset_version_id": (
                str(dataset_version_id)
                if dataset_version_id is not None
                else None
            ),
        }

    if job_type != "training":
        await asyncio.sleep(1)
        return {"message": f"Tipo de trabajo '{job_type}' no implementado aún."}

    version_id = config.get("version_id") or config.get("dataset_version_id")
    if not version_id:
        raise ValueError("Falta version_id en la configuración.")
    model_version_id = config.get("model_version_id")

    file_bytes, checksum = await asyncio.to_thread(
        fetch_training_file, client, str(version_id)
    )
    raw_data = parse_training_csv(file_bytes, checksum)
    train_data, val_data = split_training_validation(raw_data, split_ratio=0.8)
    return calculate_baseline(
        train_data,
        val_data,
        version=str(model_version_id or version_id),
        dataset_version_id=str(version_id),
        model_version_id=str(model_version_id) if model_version_id else None,
    )


async def _update_scientific_job(
    client, job_id: str, update_payload: dict[str, Any]
) -> None:
    await asyncio.to_thread(
        update_scientific_job_in_db, client, job_id, update_payload
    )


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


async def process_scientific_job(
    job_id: str,
    job_type: str,
    config: dict[str, Any],
    *,
    timeout_seconds: float | None = None,
) -> None:
    """Trabajo asíncrono con control estricto de timeout, límites, fallos y persistencia (S2-150)."""
    if supabase is None:
        return

    try:
        effective_timeout = resolve_job_timeout(
            JOB_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        )
        await _update_scientific_job(
            supabase,
            job_id,
            build_running_update_payload(_utc_now_iso()),
        )

        result = await asyncio.wait_for(
            run_scientific_algorithm(supabase, job_type, config),
            timeout=effective_timeout,
        )

        completed_payload = build_completed_update_payload(result, _utc_now_iso())
        dataset_version_id = _parse_optional_uuid_str(
            result.get("dataset_version_id")
            or config.get("version_id")
            or config.get("dataset_version_id")
        )
        model_version_id = _parse_optional_uuid_str(
            result.get("model_version_id")
            or config.get("model_version_id")
        )
        if dataset_version_id:
            completed_payload["dataset_version_id"] = dataset_version_id
        if model_version_id:
            completed_payload["model_version_id"] = model_version_id

        await _update_scientific_job(
            supabase,
            job_id,
            completed_payload,
        )

    except TimeoutError:
        logger.warning(
            "Trabajo científico %s excedió el tiempo máximo de %ss.",
            job_id,
            effective_timeout,
        )
        _persist_job_failure(
            job_id,
            build_timeout_error_message(effective_timeout),
        )

    except JobLimitExceededError as exc:
        logger.warning(
            "Trabajo científico %s excedió un límite operativo: %s",
            job_id,
            exc,
        )
        _persist_job_failure(
            job_id,
            format_limit_exceeded_error_message(exc),
        )

    except asyncio.CancelledError:
        logger.warning("Trabajo científico %s cancelado durante ejecución.", job_id)
        _persist_job_failure(
            job_id,
            "La ejecución del trabajo fue cancelada antes de completarse.",
        )
        raise

    except Exception as exc:
        logger.exception("Fallo interno procesando el trabajo científico %s.", job_id)
        _persist_job_failure(
            job_id,
            format_exception_error_message(exc),
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
    response_job = dict(job)
    if "id" in response_job:
        response_job["job_id"] = response_job.pop("id")
    return response_job


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
    if payload.job_type == "training" and isinstance(
        payload.config, TrainingConfig
    ):
        db_payload["dataset_version_id"] = str(payload.config.version_id)
    elif payload.job_type == "estimation":
        est_dataset_version = _parse_optional_uuid_str(
            config.get("dataset_version_id")
        )
        est_model_version = _parse_optional_uuid_str(
            config.get("model_version_id")
        )
        if est_dataset_version:
            db_payload["dataset_version_id"] = est_dataset_version
        if est_model_version:
            db_payload["model_version_id"] = est_model_version
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

    worker_config = {**config, "organization_id": str(organization_id)}
    background_tasks.add_task(
        process_scientific_job,
        str(inserted_job["id"]),
        payload.job_type,
        worker_config,
    )
    return build_job_accepted_response(inserted_job)
