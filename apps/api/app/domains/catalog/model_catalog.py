from datetime import date
from typing import Any
from uuid import UUID

from supabase import Client

from apps.api.app.core.database import supabase
from apps.api.app.domains.catalog.domain_catalog import (
    PUBLIC_LAKE_FIELDS,
    clean_lake_row,
    coerce_geom_to_geojson,
    coerce_station_point_to_geojson,
)
from apps.api.app.domains.catalog.schemas_catalog import (
    LakeDetail,
    LakeSummary,
    PaginatedLakes,
)


def get_active_lakes(client: Client) -> list[LakeDetail]:
    """Obtiene únicamente los lagos activos y devuelve entidades de dominio limpias."""
    response = (
        client.table("lakes")
        .select(
            "id, name, region, description, status, geom, created_at, updated_at, is_active"
        )
        .execute()
    )

    items = response.data or []
    active_lakes: list[LakeDetail] = []

    for raw_row in items:
        is_active = (
            raw_row.get("status") == "active" or raw_row.get("is_active") is True
        )
        if is_active:
            clean_row = clean_lake_row(raw_row)
            active_lakes.append(LakeDetail.model_validate(clean_row))

    return active_lakes


def get_lakes_repository(
    client: Client,
    *,
    text: str | None = None,
    region: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> PaginatedLakes:
    """Recupera lagos con filtros combinados y paginación."""
    fields = ", ".join(PUBLIC_LAKE_FIELDS)
    query = client.table("lakes").select(f"{fields}, stations(count)", count="exact")

    if text:
        query = query.ilike("name", f"%{text}%")
    if region:
        query = query.eq("region", region)
    query = query.eq("status", status_filter or "active")

    start = (page - 1) * limit
    response = query.range(start, start + limit - 1).execute()
    rows = response.data or []

    items = [LakeSummary.model_validate(clean_lake_row(row)) for row in rows]

    return PaginatedLakes(
        items=items,
        page=page,
        page_size=limit,
        total=response.count or 0,
    )


def get_lake_by_id(client: Client, lake_id: str | UUID) -> dict[str, Any]:
    """Devuelve un lago por id completo, normalizando su geometría."""
    lake_id_str = str(lake_id)
    response = client.table("lakes").select("*").eq("id", lake_id_str).execute()
    if not response.data:
        raise LookupError(f"Lago con id {lake_id_str} no existe.")

    lake = response.data[0]
    if "geom" in lake:
        lake["geom"] = coerce_geom_to_geojson(lake["geom"]) or {
            "type": "Polygon",
            "coordinates": [],
        }
    return lake


def insert_lake_in_db(client: Client, lake_data: dict[str, Any]) -> dict[str, Any] | None:
    response = client.table("lakes").insert(lake_data).execute()
    return response.data[0] if response.data else None


def update_lake_in_db(
    client: Client, lake_id: str | UUID, update_data: dict[str, Any]
) -> dict[str, Any] | None:
    response = (
        client.table("lakes").update(update_data).eq("id", str(lake_id)).execute()
    )
    return response.data[0] if response.data else None


def soft_delete_lake(client: Client, lake_id: str | UUID) -> dict[str, Any]:
    """Desactiva un lago sin borrarlo físicamente."""
    lake_id_str = str(lake_id)
    response = (
        client.table("lakes")
        .update({"status": "inactive"})
        .eq("id", lake_id_str)
        .execute()
    )
    if not response.data:
        raise LookupError(f"Lago con id {lake_id_str} no existe.")

    lake = response.data[0]
    if "geom" in lake:
        lake["geom"] = coerce_geom_to_geojson(lake["geom"]) or {
            "type": "Polygon",
            "coordinates": [],
        }
    return lake


def get_lake_stations_from_db(
    lake_id: str | UUID, status_filter: str | None = None
) -> list[dict] | None:
    """Consulta estaciones por lago con validación explícita del lago y filtro opcional."""
    lake_id_str = str(lake_id)

    lake_exists = supabase.table("lakes").select("id").eq("id", lake_id_str).execute()
    if not lake_exists.data:
        return None

    query = supabase.table("stations").select("*").eq("lake_id", lake_id_str)
    if status_filter is not None:
        query = query.eq("status", status_filter)

    stations_response = query.execute()
    return [
        {
            **station,
            "point": coerce_station_point_to_geojson(station.get("point")),
        }
        for station in (stations_response.data or [])
    ]


def get_lake_geom_by_id(client: Client, lake_id: str | UUID) -> dict[str, Any] | None:
    res = client.table("lakes").select("id, geom").eq("id", str(lake_id)).execute()
    return res.data[0] if res.data else None


def station_code_exists_in_lake(
    client: Client, lake_id: str | UUID, code: str
) -> bool:
    res = (
        client.table("stations")
        .select("id")
        .eq("lake_id", str(lake_id))
        .eq("code", code)
        .execute()
    )
    return bool(res.data and len(res.data) > 0)


def insert_station_in_db(
    client: Client, station_data: dict[str, Any]
) -> dict[str, Any] | None:
    response = client.table("stations").insert(station_data).execute()
    return response.data[0] if response.data else None


def get_station_by_id_from_db(
    client: Client, station_id: str | UUID
) -> dict[str, Any] | None:
    existing = client.table("stations").select("*").eq("id", str(station_id)).execute()
    return existing.data[0] if existing.data else None


def update_station_in_db(
    client: Client, station_id: str | UUID, update_data: dict[str, Any]
) -> dict[str, Any] | None:
    response = (
        client.table("stations")
        .update(update_data)
        .eq("id", str(station_id))
        .execute()
    )
    return response.data[0] if response.data else None


def query_lake_scenes_from_db(
    client: Client,
    lake_id: str | UUID,
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
