from typing import Any
from uuid import UUID

from apps.scientific.app.core.service_clients import (
    CoreServiceClient,
    SatelliteServiceClient,
)


def insert_prediction_in_db(
    client, db_payload: dict[str, Any]
) -> dict[str, Any] | None:
    result = (
        client.schema("scientific").table("predictions").insert(db_payload).execute()
    )
    return result.data[0] if getattr(result, "data", None) else None


def get_active_membership_for_organization(
    user_id: UUID, organization_id: UUID
) -> dict[str, Any] | None:
    return CoreServiceClient().get_organization_membership(user_id, organization_id)


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


def get_scene_metadata_in_db(scene_id: UUID) -> dict[str, Any] | None:
    return SatelliteServiceClient().get_scene_metadata(scene_id)
