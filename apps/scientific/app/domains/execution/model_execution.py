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
    return (
        insert_result.data[0]
        if getattr(insert_result, "data", None)
        else None
    )


def update_scientific_job_in_db(
    client, job_id: str, update_payload: dict[str, Any]
) -> None:
    client.table("scientific_jobs").update(update_payload).eq("id", job_id).execute()
