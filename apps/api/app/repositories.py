from typing import Any
from uuid import UUID

from app.database import supabase
from app.permissions import has_permission
from app.schemas import LakeDetail, LakeSummary, PaginatedLakes
from shapely import from_wkt
from shapely.geometry import mapping
from supabase import Client

PUBLIC_LAKE_FIELDS = (
    "id",
    "name",
    "region",
    "description",
    "status",
    "geom",
    "created_at",
    "updated_at",
)


def _convert_wkt_to_polygon(wkt_str: str) -> dict[str, Any]:
    """Convierte una geometría WKT a GeoJSON con validación explícita."""
    try:
        return mapping(from_wkt(wkt_str))
    except Exception as exc:
        raise ValueError(f"Error de integridad en geometría WKT: {exc}") from exc


def _coerce_station_point_to_geojson(value: Any) -> dict[str, Any]:
    """Normaliza el punto de PostGIS al GeoJSON esperado por los clientes."""
    if isinstance(value, dict):
        if value.get("type") != "Point":
            raise ValueError("La geometría de la estación debe ser un GeoJSON Point.")
        return value

    if not isinstance(value, str) or not value.strip():
        raise ValueError("La geometría de la estación no contiene un punto válido.")

    try:
        geometry = from_wkt(value.strip())
        if geometry.geom_type != "Point":
            raise ValueError("La geometría de la estación debe ser de tipo Point.")
        return mapping(geometry)
    except Exception as exc:
        raise ValueError(
            f"Error de integridad en el punto de la estación: {exc}"
        ) from exc


def _coerce_geom_to_geojson(value: Any) -> dict[str, Any] | None:
    """Convierte geometrías WKT a GeoJSON para que la entidad de dominio permanezca limpia."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None

    return _convert_wkt_to_polygon(candidate)


def _clean_lake_row(raw_row: dict[str, Any]) -> dict[str, Any]:
    """Filtra columnas internas y devuelve la representación pública de un lago."""
    cleaned: dict[str, Any] = {}

    for field in PUBLIC_LAKE_FIELDS:
        if field in raw_row and raw_row[field] is not None:
            cleaned[field] = raw_row[field]

    if raw_row.get("is_active") is True:
        cleaned["status"] = "active"
    elif "status" in cleaned:
        cleaned["status"] = str(cleaned["status"])
    else:
        cleaned["status"] = "inactive"

    if "geom" in raw_row:
        cleaned["geom"] = _coerce_geom_to_geojson(raw_row["geom"]) or {
            "type": "Polygon",
            "coordinates": [],
        }

    return cleaned


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
            clean_row = _clean_lake_row(raw_row)
            active_lakes.append(LakeDetail.model_validate(clean_row))

    return active_lakes


def get_active_memberships(client: Client, user_id: UUID) -> list[dict]:
    """Return only active memberships belonging to active organizations."""
    response = (
        client.table("memberships")
        .select("id, role, status, organization:organizations!inner(id, name, status)")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .execute()
    )

    return response.data or []


def count_active_lakes(client: Client) -> int:
    response = (
        client.table("lakes")
        .select("id", count="exact", head=True)
        .eq("status", "active")
        .execute()
    )
    return response.count or 0


def count_active_stations(client: Client) -> int:
    response = (
        client.table("stations")
        .select("id", count="exact", head=True)
        .eq("status", "active")
        .execute()
    )
    return response.count or 0


def count_visible_organizations(client: Client, user_data: dict) -> int:
    if has_permission(user_data, "admin"):
        response = (
            client.table("organizations")
            .select("id", count="exact", head=True)
            .eq("status", "active")
            .execute()
        )
        return response.count or 0

    user_id = user_data.get("sub") or user_data.get("id")
    if not user_id:
        return 0

    response = (
        client.table("memberships")
        .select("organization_id, organizations!inner(id)", count="exact", head=True)
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .eq("organizations.status", "active")
        .execute()
    )
    return response.count or 0


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
            "point": _coerce_station_point_to_geojson(station.get("point")),
        }
        for station in (stations_response.data or [])
    ]


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
    query = client.table("lakes").select(", ".join(PUBLIC_LAKE_FIELDS), count="exact")

    if text:
        query = query.ilike("name", f"%{text}%")
    if region:
        query = query.eq("region", region)
    query = query.eq("status", status_filter or "active")

    start = (page - 1) * limit
    response = query.range(start, start + limit - 1).execute()
    rows = response.data or []

    items = [LakeSummary.model_validate(_clean_lake_row(row)) for row in rows]

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
        lake["geom"] = _coerce_geom_to_geojson(lake["geom"]) or {
            "type": "Polygon",
            "coordinates": [],
        }
    return lake


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
        lake["geom"] = _coerce_geom_to_geojson(lake["geom"]) or {
            "type": "Polygon",
            "coordinates": [],
        }
    return lake
