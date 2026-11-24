"""Persistencia de artefactos de modelos y referencias a trabajos científicos."""

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from postgrest.exceptions import APIError


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
    job = str(job_id).strip()
    name = filename.strip().replace("\\", "/").split("/")[-1]
    if not job:
        raise ValueError("job_id no puede estar vacío.")
    if not name or name in {".", ".."}:
        raise ValueError("filename no puede estar vacío.")
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
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("filename no puede estar vacío.")
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("bucket no puede estar vacío.")

    normalized_job_id = str(job_id).strip()
    if not normalized_job_id:
        raise ValueError("job_id no puede estar vacío.")

    storage_path = build_model_artifact_storage_path(normalized_job_id, filename)
    checksum = calculate_sha256(artifact_bytes)
    storage = client.storage.from_(bucket)

    storage.upload(
        storage_path,
        artifact_bytes,
        {"content-type": "application/octet-stream"},
    )

    try:
        select_result = (
            client.table("scientific_jobs")
            .select("result")
            .eq("id", normalized_job_id)
            .limit(1)
            .execute()
        )
        rows = getattr(select_result, "data", None) or []
        previous_result = rows[0].get("result") if rows else None
        result = dict(previous_result) if isinstance(previous_result, dict) else {}
        result["model_artifact"] = {
            "job_id": normalized_job_id,
            "bucket": bucket,
            "storage_path": storage_path,
            "checksum": checksum,
            "size_bytes": len(artifact_bytes),
        }

        (
            client.table("scientific_jobs")
            .update({"result": result})
            .eq("id", normalized_job_id)
            .execute()
        )
    except (APIError, RuntimeError, OSError, ValueError):
        try:
            storage.remove([storage_path])
        except (APIError, RuntimeError, OSError, ValueError):
            pass
        raise

    return ModelArtifactReference(
        job_id=normalized_job_id,
        bucket=bucket,
        storage_path=storage_path,
        checksum=checksum,
        size_bytes=len(artifact_bytes),
    )
