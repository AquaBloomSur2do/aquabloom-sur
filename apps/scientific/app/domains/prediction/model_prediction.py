from typing import Any
from uuid import UUID


def insert_prediction_in_db(
    client, db_payload: dict[str, Any]
) -> dict[str, Any] | None:
    result = (
        client.schema("scientific").table("predictions").insert(db_payload).execute()
    )
    return result.data[0] if getattr(result, "data", None) else None


def get_active_membership_for_organization(
    client, user_id: UUID, organization_id: UUID
) -> dict[str, Any] | None:
    result = (
        client.table("memberships")
        .select("organization_id, role, status, organizations!inner(id, status)")
        .eq("user_id", str(user_id))
        .eq("organization_id", str(organization_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .limit(1)
        .execute()
    )
    rows = getattr(result, "data", None) or []
    return rows[0] if rows else None


def get_prediction_by_id_in_db(
    client, prediction_id: UUID, organization_id: UUID
) -> dict[str, Any] | None:
    result = (
        client.schema("scientific")
        .table("predictions")
        .select("*")
        .eq("id", str(prediction_id))
        .eq("organization_id", str(organization_id))
        .limit(1)
        .execute()
    )
    rows = getattr(result, "data", None) or []
    return rows[0] if rows else None


def get_scene_metadata_in_db(client, scene_id: UUID) -> dict[str, Any] | None:
    result = (
        client.schema("satellite")
        .table("scenes")
        .select("id, lake_id, scene_identifier, acquisition_date, is_experimental")
        .eq("id", str(scene_id))
        .limit(1)
        .execute()
    )
    rows = getattr(result, "data", None) or []
    return rows[0] if rows else None


def get_training_job_origin_in_db(
    client,
    *,
    organization_id: UUID,
    training_job_id: UUID | None = None,
    model_version_id: UUID | None = None,
    dataset_version_id: UUID | None = None,
) -> dict[str, Any] | None:
    query = (
        client.table("scientific_jobs")
        .select("id, config, result, dataset_version_id, model_version_id")
        .eq("organization_id", str(organization_id))
        .eq("job_type", "training")
    )
    if training_job_id is not None:
        query = query.eq("id", str(training_job_id))
    elif model_version_id is not None:
        query = query.eq("model_version_id", str(model_version_id))
    elif dataset_version_id is not None:
        query = query.eq("dataset_version_id", str(dataset_version_id))
    else:
        return None

    result = query.limit(1).execute()
    rows = getattr(result, "data", None) or []
    return rows[0] if rows else None
