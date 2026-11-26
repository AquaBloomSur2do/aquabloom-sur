from datetime import date
from typing import Any
from uuid import UUID


def lake_exists_in_db(client, lake_id: UUID) -> bool:
    lakes = client.table("lakes").select("id").eq("id", str(lake_id)).execute()
    return bool(lakes.data)


def get_scene_metadata_by_id(client, scene_id: UUID) -> dict[str, Any] | None:
    response = (
        client.table("scenes")
        .select("id, lake_id, scene_identifier, acquisition_date, is_experimental")
        .eq("id", str(scene_id))
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


def query_scenes_by_lake_and_dates(
    client,
    *,
    lake_id: UUID,
    start_date: date,
    end_date: date,
    offset: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    response = (
        client.table("scenes")
        .select(
            "id, lake_id, scene_identifier, acquisition_date, created_at",
            count="exact",
        )
        .eq("lake_id", str(lake_id))
        .gte("acquisition_date", start_date.isoformat())
        .lte("acquisition_date", end_date.isoformat())
        .order("acquisition_date", desc=True)
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return response.data or [], response.count or 0
