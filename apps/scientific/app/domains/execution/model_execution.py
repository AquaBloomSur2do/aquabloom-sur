from typing import Any
from uuid import UUID

from apps.scientific.app.core.service_clients import (
    CoreServiceClient,
    ServiceContractError,
)
from apps.scientific.app.dataset_consumer import DatasetContractError


def has_active_organization_membership(user_id: UUID, organization_id: UUID) -> bool:
    return CoreServiceClient().has_active_organization_membership(
        user_id,
        organization_id,
    )


def get_dataset_version_for_training(
    version_id: UUID | str, organization_id: UUID | str
) -> dict[str, Any] | None:
    return CoreServiceClient().get_dataset_version_for_training(
        version_id,
        organization_id,
    )


def fetch_training_file(
    version_id: UUID | str,
    organization_id: UUID | str,
    user_id: UUID | str,
) -> tuple[bytes, str]:
    """Obtiene el archivo de entrenamiento mediante el contrato interno de Core."""
    try:
        return CoreServiceClient().download_training_file(
            version_id,
            organization_id,
            user_id,
        )
    except (DatasetContractError, ServiceContractError) as exc:
        raise ValueError(
            "No se pudo obtener el archivo de entrenamiento desde Core."
        ) from exc


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
