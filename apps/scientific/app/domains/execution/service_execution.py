import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from postgrest.exceptions import APIError

from apps.scientific.app.core.config import settings
from apps.scientific.app.core.correlation import resolve_correlation_id
from apps.scientific.app.core.database import supabase
from apps.scientific.app.domains.execution.domain_execution import (
    JobLimitExceededError,
    build_completed_update_payload,
    build_failure_update_payload,
    build_job_accepted_response,
    build_running_update_payload,
    build_timeout_error_message,
    calculate_baseline,
    execute_point_inference,
    format_exception_error_message,
    format_limit_exceeded_error_message,
    job_matches_request,
    parse_training_csv,
    resolve_job_timeout,
    split_training_validation,
    validate_and_normalize_inference_points,
    verify_and_deserialize_model_artifact,
)
from apps.scientific.app.domains.execution.model_execution import (
    download_model_artifact_from_storage,
    fetch_training_file,
    find_scientific_job_in_db,
    get_dataset_version_for_training,
    get_registered_model_artifact_ref,
    get_training_origin_for_estimation,
    has_active_organization_membership,
    insert_scientific_job_in_db,
    update_scientific_job_in_db,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    EstimationConfig,
    JobCreate,
    ReproducibilityMetadata,
    TrainingConfig,
    TrainingPartitionMetadata,
)

logger = logging.getLogger(__name__)
JOB_TIMEOUT_SECONDS = settings.job_timeout_seconds
TRAINING_SPLIT_RATIO = 0.8


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_optional_uuid_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


def _persist_job_failure(job_id: str, error_message: str, correlation_id: str) -> None:
    """Persiste el estado fallido del trabajo sin propagar fallos secundarios de BD."""
    if supabase is None:
        return
    try:
        update_scientific_job_in_db(
            supabase,
            job_id,
            build_failure_update_payload(error_message, _utc_now_iso()),
        )
    except (APIError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        logger.exception(
            "No se pudo persistir el estado fallido para el trabajo %s | correlation_id=%s.",
            job_id,
            correlation_id,
            extra={"correlation_id": correlation_id, "job_id": job_id},
        )


async def run_scientific_algorithm(
    client,
    job_type: str,
    config: dict[str, Any],
    *,
    organization_id: UUID | str | None = None,
    requested_by: UUID | str | None = None,
) -> dict[str, Any]:
    """Orquesta la carga de datos y el procesamiento del trabajo científico."""
    if job_type == "estimation":
        model_id = config.get("model_id")
        scene_id = config.get("scene_id")
        points = config.get("points")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("Falta model_id en la configuración.")
        if not isinstance(scene_id, str) or not scene_id.strip():
            raise ValueError("Falta scene_id en la configuración.")
        normalized_model_id = model_id.strip()
        normalized_scene_id = scene_id.strip()
        normalized_points = (
            validate_and_normalize_inference_points(points)
            if points is not None
            else None
        )

        effective_org_id = str(organization_id).strip() if organization_id else None
        raw_training_job_id = config.get("training_job_id")
        raw_model_version_id = config.get("model_version_id")
        explicit_origin_requested = bool(
            raw_training_job_id or raw_model_version_id
        )
        if normalized_points is not None and not effective_org_id:
            raise ValueError("Falta organization_id para ejecutar la inferencia.")

        lookup_model_version_id = (
            _parse_optional_uuid_str(raw_model_version_id)
            or _parse_optional_uuid_str(normalized_model_id)
        )

        origin_job = await asyncio.to_thread(
            get_training_origin_for_estimation,
            client,
            organization_id=effective_org_id or "",
            training_job_id=(
                str(raw_training_job_id) if raw_training_job_id else None
            ),
            model_version_id=lookup_model_version_id,
            lookup_model_id=_parse_optional_uuid_str(normalized_model_id),
        )

        provenance_result: dict[str, Any] = {}
        if origin_job is None and (
            explicit_origin_requested or normalized_points is not None
        ):
            raise ValueError(
                "No se encontró el trabajo de entrenamiento de origen del modelo."
            )

        if origin_job is not None:
            if str(origin_job.get("status", "")).lower() != "completed":
                raise ValueError(
                    "El trabajo de entrenamiento de origen aún no está completado."
                )

            origin_config = (
                origin_job.get("config")
                if isinstance(origin_job.get("config"), dict)
                else {}
            )
            origin_result = (
                origin_job.get("result")
                if isinstance(origin_job.get("result"), dict)
                else {}
            )
            resolved_training_job_id = _parse_optional_uuid_str(
                origin_job.get("id")
            )
            dataset_id = (
                origin_config.get("dataset_id")
                or origin_result.get("dataset_id")
            )
            dataset_version_id = (
                origin_job.get("dataset_version_id")
                or origin_config.get("version_id")
                or origin_result.get("dataset_version_id")
            )
            resolved_model_version_id = (
                origin_job.get("model_version_id")
                or origin_result.get("model_version_id")
                or lookup_model_version_id
            )
            source_model_version_id = _parse_optional_uuid_str(
                origin_job.get("model_version_id")
                or origin_result.get("model_version_id")
            )
            requested_model_version_id = _parse_optional_uuid_str(
                raw_model_version_id
            )
            if requested_model_version_id is not None and (
                source_model_version_id is not None
                and source_model_version_id != requested_model_version_id
            ):
                raise ValueError(
                    "El entrenamiento de origen no corresponde al modelo indicado."
                )
            if requested_model_version_id is not None and (
                source_model_version_id is None
                and resolved_training_job_id != requested_model_version_id
            ):
                raise ValueError(
                    "El entrenamiento de origen no corresponde al modelo indicado."
                )
            if normalized_points is not None and (
                resolved_training_job_id
                != _parse_optional_uuid_str(normalized_model_id)
            ):
                raise ValueError(
                    "El artefacto de inferencia no corresponde al entrenamiento de origen."
                )

            resolved_dataset_id = _parse_optional_uuid_str(dataset_id)
            resolved_dataset_version_id = _parse_optional_uuid_str(
                dataset_version_id
            )
            if (
                resolved_training_job_id is None
                or resolved_dataset_id is None
                or resolved_dataset_version_id is None
            ):
                raise ValueError(
                    "El entrenamiento de origen no informa el dataset y su versión."
                )

            raw_model_name = config.get("model_name") or origin_result.get("model")
            resolved_model_name = (
                raw_model_name.strip()
                if isinstance(raw_model_name, str) and raw_model_name.strip()
                else None
            )
            provenance_result = {
                "model_id": normalized_model_id,
                "model_name": resolved_model_name,
                "model_version_id": _parse_optional_uuid_str(
                    resolved_model_version_id
                ),
                "training_job_id": resolved_training_job_id,
                "dataset_id": resolved_dataset_id,
                "dataset_version_id": resolved_dataset_version_id,
            }

        if points is None:
            await asyncio.sleep(1)
            if provenance_result:
                return {
                    "status": "completed",
                    "scene_id": normalized_scene_id,
                    **provenance_result,
                }
            return {"message": "Tipo de trabajo 'estimation' no implementado aún."}

        artifact_ref = await asyncio.to_thread(
            get_registered_model_artifact_ref,
            client,
            normalized_model_id,
            effective_org_id,
        )
        artifact_bytes = await asyncio.to_thread(
            download_model_artifact_from_storage,
            client,
            artifact_ref["bucket"],
            artifact_ref["storage_path"],
        )
        artifact = verify_and_deserialize_model_artifact(
            artifact_bytes, artifact_ref["checksum"]
        )
        predictions = execute_point_inference(artifact, normalized_points)
        model_type = "baseline" if "prediction_value" in artifact else "linear"
        result: dict[str, Any] = {
            "model_id": normalized_model_id,
            "scene_id": normalized_scene_id,
            "model_type": model_type,
            "artifact_checksum": artifact_ref["checksum"],
            "point_count": len(predictions),
            "predictions": predictions,
            **provenance_result,
        }
        if model_type == "baseline":
            result["baseline"] = artifact.get("strategy", "baseline")
        return result

    if job_type != "training":
        await asyncio.sleep(1)
        return {"message": f"Tipo de trabajo '{job_type}' no implementado aún."}

    version_id = config.get("version_id") or config.get("dataset_version_id")
    if not version_id:
        raise ValueError("Falta version_id en la configuración.")
    if organization_id is None or requested_by is None:
        raise ValueError(
            "organization_id y requested_by son necesarios para consultar Core."
        )
    model_version_id = config.get("model_version_id")

    file_bytes, checksum = await asyncio.to_thread(
        fetch_training_file,
        str(version_id),
        organization_id,
        requested_by,
    )
    raw_data = parse_training_csv(file_bytes, checksum)
    train_data, val_data = split_training_validation(
        raw_data, split_ratio=TRAINING_SPLIT_RATIO
    )
    result = calculate_baseline(
        train_data,
        val_data,
        version=str(model_version_id or version_id),
        dataset_version_id=str(version_id),
        model_version_id=str(model_version_id) if model_version_id else None,
    )
    result["reproducibility"] = ReproducibilityMetadata(
        dataset_version_id=str(version_id),
        partition=TrainingPartitionMetadata(
            strategy="sequential",
            split_ratio=TRAINING_SPLIT_RATIO,
            train_sample_count=result["baseline"]["train_sample_count"],
            validation_sample_count=result["baseline"]["validation_sample_count"],
        ),
        seed=None,
        configuration={
            "algorithm": result["model"],
            "baseline_strategy": result["baseline"]["strategy"],
            "training_config": config,
            "split_strategy": "sequential",
            "split_ratio": TRAINING_SPLIT_RATIO,
        },
        code_version=os.getenv("APP_VERSION") or "dev",
        environment=settings.environment,
    ).model_dump(mode="json")
    return result


async def _update_scientific_job(
    client, job_id: str, update_payload: dict[str, Any]
) -> None:
    await asyncio.to_thread(update_scientific_job_in_db, client, job_id, update_payload)


def validate_training_version_service(
    config: TrainingConfig, organization_id: UUID
) -> None:
    version = get_dataset_version_for_training(config.version_id, organization_id)
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
    correlation_id: str | None = None,
    timeout_seconds: float | None = None,
    organization_id: UUID | str | None = None,
    requested_by: UUID | str | None = None,
) -> None:
    """Trabajo asíncrono con control estricto de timeout, límites, fallos y persistencia (S2-150)."""
    if supabase is None:
        return

    correlation_id = resolve_correlation_id(correlation_id)
    log_context = {"correlation_id": correlation_id, "job_id": job_id}
    logger.info(
        "Ejecución científica iniciada | correlation_id=%s",
        correlation_id,
        extra=log_context,
    )

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
            run_scientific_algorithm(
                supabase,
                job_type,
                config,
                organization_id=organization_id,
                requested_by=requested_by,
            ),
            timeout=effective_timeout,
        )

        completed_payload = build_completed_update_payload(result, _utc_now_iso())
        if job_type == "estimation":
            dataset_version_id = _parse_optional_uuid_str(
                result.get("dataset_version_id")
            )
            model_version_id = _parse_optional_uuid_str(
                result.get("model_version_id")
            )
        else:
            dataset_version_id = _parse_optional_uuid_str(
                result.get("dataset_version_id")
                or config.get("version_id")
                or config.get("dataset_version_id")
            )
            model_version_id = _parse_optional_uuid_str(
                result.get("model_version_id")
                or config.get("model_version_id")
                or config.get("model_id")
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
        logger.info(
            "Ejecución científica completada | correlation_id=%s",
            correlation_id,
            extra=log_context,
        )

    except TimeoutError:
        logger.warning(
            "Trabajo científico %s excedió el tiempo máximo de %ss | correlation_id=%s",
            job_id,
            effective_timeout,
            correlation_id,
            extra=log_context,
        )
        _persist_job_failure(
            job_id,
            build_timeout_error_message(effective_timeout),
            correlation_id,
        )

    except JobLimitExceededError as exc:
        logger.warning(
            "Trabajo científico %s excedió un límite operativo: %s | correlation_id=%s",
            job_id,
            exc,
            correlation_id,
            extra=log_context,
        )
        _persist_job_failure(
            job_id,
            format_limit_exceeded_error_message(exc),
            correlation_id,
        )

    except asyncio.CancelledError:
        logger.warning(
            "Trabajo científico %s cancelado durante ejecución | correlation_id=%s",
            job_id,
            correlation_id,
            extra=log_context,
        )
        _persist_job_failure(
            job_id,
            "La ejecución del trabajo fue cancelada antes de completarse.",
            correlation_id,
        )
        raise

    except (APIError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.exception(
            "Fallo interno procesando el trabajo científico %s | correlation_id=%s",
            job_id,
            correlation_id,
            extra=log_context,
        )
        _persist_job_failure(
            job_id,
            format_exception_error_message(exc),
            correlation_id,
        )


def validate_job_organization_service(user_id: UUID, organization_id: UUID) -> None:
    if not has_active_organization_membership(user_id, organization_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo.",
        )


def get_job_status_service(
    client, job_id: UUID, user_id: UUID, organization_id: UUID
) -> dict[str, Any]:
    validate_job_organization_service(user_id, organization_id)
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
    result = response_job.get("result")
    if isinstance(result, dict):
        response_job["traceability_evidence"] = result.get("traceability_evidence")
    return response_job


def create_execution_job_service(
    client,
    *,
    payload: JobCreate,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None,
    user_id: UUID,
    organization_id: UUID,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    correlation_id = resolve_correlation_id(correlation_id)
    log_context = {"correlation_id": correlation_id}
    validate_job_organization_service(user_id, organization_id)
    config = payload.config.model_dump(mode="json")

    if idempotency_key is not None:
        existing_job = find_scientific_job_in_db(
            client,
            idempotency_key=idempotency_key,
            organization_id=organization_id,
        )
        if existing_job is not None:
            if job_matches_request(existing_job, payload, config):
                logger.info(
                    "Trabajo científico ya existente reutilizado | correlation_id=%s",
                    correlation_id,
                    extra={
                        **log_context,
                        "job_id": str(
                            existing_job.get("id") or existing_job.get("job_id")
                        ),
                    },
                )
                return build_job_accepted_response(existing_job)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La clave de idempotencia ya fue utilizada con un contenido diferente.",
            )

    if payload.job_type == "training":
        validate_training_version_service(payload.config, organization_id)

    db_payload: dict[str, Any] = {
        "job_type": payload.job_type,
        "config": config,
        "status": "queued",
        "organization_id": str(organization_id),
        "requested_by": str(user_id),
    }
    if payload.job_type == "training" and isinstance(payload.config, TrainingConfig):
        db_payload["dataset_version_id"] = str(payload.config.version_id)
    if payload.job_type == "estimation" and isinstance(
        payload.config, EstimationConfig
    ):
        est_model_version = _parse_optional_uuid_str(
            config.get("model_version_id") or config.get("model_id")
        )
        db_payload["model_version_id"] = (
            est_model_version or str(payload.config.model_id)
        )
        db_payload["scene_id"] = str(payload.config.scene_id)
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
        process_scientific_job,
        str(inserted_job["id"]),
        payload.job_type,
        config,
        organization_id=organization_id,
        requested_by=user_id,
        correlation_id=correlation_id,
    )
    logger.info(
        "Trabajo científico aceptado y enviado a BackgroundTasks | correlation_id=%s",
        correlation_id,
        extra={**log_context, "job_id": str(inserted_job["id"])},
    )
    return build_job_accepted_response(inserted_job)
