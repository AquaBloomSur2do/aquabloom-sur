from typing import Any
from uuid import UUID

from storage3.utils import StorageException


def has_active_organization_membership(
    client, user_id: UUID, organization_id: UUID
) -> bool:
    rows = (
        client.table("memberships")
        .select("organization_id, organizations!inner(id, status)")
        .eq("user_id", str(user_id))
        .eq("organization_id", str(organization_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def get_dataset_version_for_training(
    client, version_id: UUID | str
) -> dict[str, Any] | None:
    rows = (
        client.schema("dataset")
        .table("versions")
        .select("id, dataset_id, state, status")
        .eq("id", str(version_id))
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def fetch_training_file(client, version_id: UUID | str) -> tuple[bytes, str]:
    """Obtiene el archivo de entrenamiento y su checksum desde Supabase."""
    manifests = (
        client.schema("dataset")
        .table("training_manifests")
        .select("storage_path, checksum")
        .eq("version_id", str(version_id))
        .limit(1)
        .execute()
        .data
        or []
    )
    if not manifests:
        raise ValueError("Manifiesto de la versión no encontrado.")

    manifest = manifests[0]
    storage_path = manifest.get("storage_path")
    checksum = manifest.get("checksum")
    if (
        not isinstance(storage_path, str)
        or not storage_path
        or not isinstance(checksum, str)
        or len(checksum) != 64
    ):
        raise ValueError("El manifiesto del archivo de entrenamiento no es válido.")

    try:
        file_bytes = client.storage.from_("training_files").download(storage_path)
    except StorageException as exc:
        raise ValueError("Archivo de entrenamiento no encontrado.") from exc

    return file_bytes, checksum


def get_registered_model_artifact_ref(
    client, model_id: UUID | str, organization_id: UUID | str
) -> dict[str, Any]:
    """Obtiene la referencia del artefacto desde el trabajo científico."""
    normalized_model_id = str(model_id).strip()
    if not normalized_model_id:
        raise ValueError("model_id no puede estar vacío.")
    normalized_org_id = str(organization_id).strip()
    if not normalized_org_id:
        raise ValueError("organization_id no puede estar vacío.")

    jobs = (
        client.table("scientific_jobs")
        .select("result")
        .eq("id", normalized_model_id)
        .eq("organization_id", normalized_org_id)
        .eq("job_type", "training")
        .eq("status", "completed")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not jobs:
        raise ValueError("Artefacto del modelo no encontrado.")

    result = jobs[0].get("result")
    if not isinstance(result, dict):
        raise TypeError("El trabajo no contiene una referencia de artefacto.")
    artifact_ref = result.get("model_artifact")
    if not isinstance(artifact_ref, dict):
        raise TypeError("El trabajo no contiene una referencia de artefacto.")

    bucket = artifact_ref.get("bucket")
    storage_path = artifact_ref.get("storage_path")
    checksum = artifact_ref.get("checksum")
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("La referencia del artefacto no contiene bucket.")
    if not isinstance(storage_path, str) or not storage_path.strip():
        raise ValueError("La referencia del artefacto no contiene storage_path.")
    if (
        not isinstance(checksum, str)
        or len(checksum) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in checksum)
    ):
        raise ValueError("La referencia del artefacto no contiene checksum válido.")
    return {
        "bucket": bucket.strip(),
        "storage_path": storage_path.strip(),
        "checksum": checksum,
    }


def download_model_artifact_from_storage(
    client, bucket: str, storage_path: str
) -> bytes:
    """Descarga el artefacto desde Supabase Storage."""
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("bucket no puede estar vacío.")
    if not isinstance(storage_path, str) or not storage_path.strip():
        raise ValueError("storage_path no puede estar vacío.")
    normalized_bucket = bucket.strip()
    normalized_storage_path = storage_path.strip()

    try:
        artifact_bytes = client.storage.from_(normalized_bucket).download(
            normalized_storage_path
        )
    except StorageException as exc:
        raise ValueError("Artefacto del modelo no encontrado en Storage.") from exc
    if not isinstance(artifact_bytes, bytes):
        raise TypeError("El artefacto descargado no contiene bytes válidos.")
    return artifact_bytes


def find_scientific_job_in_db(
    client,
    *,
    organization_id: UUID | str,
    job_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any] | None:
    query = (
        client.table("scientific_jobs")
        .select("*")
        .eq("organization_id", str(organization_id))
    )
    if job_id is not None:
        query = query.eq("id", job_id)
    elif idempotency_key is not None:
        query = query.eq("idempotency_key", idempotency_key)
    else:
        raise ValueError("Se requiere job_id o idempotency_key.")

    result = query.limit(1).execute()
    return result.data[0] if getattr(result, "data", None) else None


def insert_scientific_job_in_db(
    client, db_payload: dict[str, Any]
) -> dict[str, Any] | None:
    insert_result = client.table("scientific_jobs").insert(db_payload).execute()
    return insert_result.data[0] if getattr(insert_result, "data", None) else None


def update_scientific_job_in_db(
    client, job_id: str, update_payload: dict[str, Any]
) -> None:
    client.table("scientific_jobs").update(update_payload).eq("id", job_id).execute()
