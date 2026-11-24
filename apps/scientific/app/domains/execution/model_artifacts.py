"""Persistencia de artefactos de modelos y referencias a trabajos científicos."""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelArtifactReference:
    job_id: str
    bucket: str
    storage_path: str
    checksum: str
    size_bytes: int


def calculate_sha256(artifact_bytes: bytes) -> str:
    """Calcula el SHA-256 de los bytes del artefacto."""
    if not isinstance(artifact_bytes, bytes):
        raise TypeError("artifact_bytes debe ser bytes.")
    return hashlib.sha256(artifact_bytes).hexdigest()


def build_model_artifact_storage_path(job_id: str | UUID, filename: str) -> str:
    """Construye una ruta Storage segura dentro de models/{job_id}/."""
    if not isinstance(job_id, (str, UUID)):
        raise TypeError("job_id debe ser un UUID.")
    try:
        job = str(UUID(str(job_id).strip()))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("job_id debe ser un UUID válido.") from exc

    if not isinstance(filename, str):
        raise TypeError("filename debe ser texto.")
    name = filename.strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("filename no puede estar vacío ni contener rutas.")
    return str(PurePosixPath("models") / job / name)


def save_model_artifact(
    client: Any,
    job_id: str | UUID,
    artifact_bytes: bytes,
    filename: str = "model.pkl",
    bucket: str = "model_artifacts",
) -> ModelArtifactReference:
    """Sube un artefacto y registra su referencia en el trabajo científico."""
    if not isinstance(artifact_bytes, bytes):
        raise TypeError("artifact_bytes debe ser bytes.")
    if not artifact_bytes:
        raise ValueError("artifact_bytes no puede estar vacío.")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename no puede estar vacío.")
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("bucket no puede estar vacío.")

    normalized_bucket = bucket.strip()
    try:
        normalized_job_id = str(UUID(str(job_id).strip()))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("job_id debe ser un UUID válido.") from exc

    storage_path = build_model_artifact_storage_path(normalized_job_id, filename)
    checksum = calculate_sha256(artifact_bytes)
    storage = client.storage.from_(normalized_bucket)
    uploaded = False

    try:
        select_result = (
            client.table("scientific_jobs")
            .select("result")
            .eq("id", normalized_job_id)
            .limit(1)
            .execute()
        )
        rows = getattr(select_result, "data", None) or []
        if not rows:
            raise ValueError("El trabajo científico no existe.")

        previous_result = rows[0].get("result")
        result = dict(previous_result) if isinstance(previous_result, dict) else {}
        result["model_artifact"] = {
            "job_id": normalized_job_id,
            "bucket": normalized_bucket,
            "storage_path": storage_path,
            "checksum": checksum,
            "size_bytes": len(artifact_bytes),
        }

        uploaded = True
        storage.upload(
            storage_path,
            artifact_bytes,
            {"content-type": "application/octet-stream"},
        )

        update_result = (
            client.table("scientific_jobs")
            .update({"result": result})
            .eq("id", normalized_job_id)
            .execute()
        )
        updated_rows = getattr(update_result, "data", None) or []
        if not updated_rows:
            raise ValueError("El trabajo científico no pudo actualizarse.")
    except Exception:
        try:
            if uploaded:
                storage.remove([storage_path])
        except Exception as cleanup_error:
            logger.exception(
                "No se pudo limpiar el artefacto %s después de fallar la persistencia.",
                storage_path,
                exc_info=cleanup_error,
            )
        raise

    return ModelArtifactReference(
        job_id=normalized_job_id,
        bucket=normalized_bucket,
        storage_path=storage_path,
        checksum=checksum,
        size_bytes=len(artifact_bytes),
    )
