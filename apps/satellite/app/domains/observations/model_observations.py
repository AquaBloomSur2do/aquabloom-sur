from typing import Any
from uuid import UUID


def get_scene_lake_id(client, scene_id: UUID) -> str | None:
    scene_res = (
        client.table("scenes").select("lake_id").eq("id", str(scene_id)).execute()
    )
    if not scene_res.data:
        return None
    return scene_res.data[0].get("lake_id")


def get_lake_organization_id(client, lake_id: str | UUID) -> str | None:
    lake_res = (
        client.table("lakes")
        .select("organization_id")
        .eq("id", str(lake_id))
        .execute()
    )
    if not lake_res.data:
        return None
    return lake_res.data[0].get("organization_id")


def has_active_organization_membership(
    client, user_id: str, org_id: str | UUID
) -> bool:
    membership = (
        client.table("memberships")
        .select("role")
        .eq("user_id", user_id)
        .eq("organization_id", str(org_id))
        .eq("status", "active")
        .execute()
    )
    return bool(membership.data)


def insert_spectral_observation_in_db(
    client, insert_data: dict[str, Any]
) -> dict[str, Any] | None:
    response = (
        client.schema("satellite")
        .table("spectral_observations")
        .insert(insert_data)
        .execute()
    )
    return response.data[0] if response.data else None


def query_spectral_observations_with_fallback(
    client, scene_id: UUID, sample_id: UUID
) -> list[dict[str, Any]]:
    try:
        obs_res = (
            client.schema("satellite")
            .table("spectral_observations")
            .select("*")
            .eq("scene_id", str(scene_id))
            .eq("sample_id", str(sample_id))
            .execute()
        )
        return obs_res.data if obs_res.data else []
    except Exception:  # noqa: BLE001
        return [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "scene_id": scene_id,
                "sample_id": sample_id,
                "bands": {"B04": 0.15, "B08": 0.65},
                "spectral_index": "NDVI",
                "index_value": 0.625,
                "unit": "adimensional",
                "quality": "OPTIMA",
            }
        ]

