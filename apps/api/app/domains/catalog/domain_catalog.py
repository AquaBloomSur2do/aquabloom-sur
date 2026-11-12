from typing import Any

from shapely import from_wkt
from shapely.geometry import Point, mapping, shape

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


def validate_station_inside_lake(
    lake_geojson: dict | str, lat: float, lon: float
) -> None:
    """Valida topológicamente que un punto (lon, lat) esté cubierto por el polígono del lago."""
    if lake_geojson is None:
        raise ValueError("La geometría del lago no es válida.")

    try:
        if isinstance(lake_geojson, str):
            lake_polygon = from_wkt(lake_geojson.strip())
        else:
            lake_polygon = shape(lake_geojson)
    except Exception as exc:
        raise ValueError("La geometría del lago no es válida.") from exc

    station_point = Point(lon, lat)
    if not lake_polygon.covers(station_point):
        raise ValueError(
            "Las coordenadas de la estación están fuera del polígono del lago."
        )


def convert_wkt_to_polygon(wkt_str: str) -> dict[str, Any]:
    """Convierte una geometría WKT a GeoJSON con validación explícita."""
    try:
        return mapping(from_wkt(wkt_str))
    except Exception as exc:
        raise ValueError(f"Error de integridad en geometría WKT: {exc}") from exc


def convert_polygon_to_wkt(geom: dict) -> str | None:
    """Convierte un diccionario GeoJSON Polygon a una cadena WKT para PostGIS."""
    if not geom or geom.get("type") != "Polygon":
        return None
    rings = []
    for ring in geom.get("coordinates", []):
        points = ", ".join([f"{lon} {lat}" for lon, lat in ring])
        rings.append(f"({points})")
    return f"POLYGON({', '.join(rings)})"


def coerce_station_point_to_geojson(value: Any) -> dict[str, Any]:
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


def coerce_geom_to_geojson(value: Any) -> dict[str, Any] | None:
    """Convierte geometrías WKT a GeoJSON para que la entidad de dominio permanezca limpia."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    candidate = value.strip()
    if not candidate:
        return None

    return convert_wkt_to_polygon(candidate)


def clean_lake_row(raw_row: dict[str, Any]) -> dict[str, Any]:
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
        cleaned["geom"] = coerce_geom_to_geojson(raw_row["geom"]) or {
            "type": "Polygon",
            "coordinates": [],
        }
    if "stations" in raw_row:
        stations_data = raw_row["stations"]
        if isinstance(stations_data, list) and len(stations_data) > 0:
            cleaned["stations_count"] = stations_data[0].get("count", 0)
        elif isinstance(stations_data, dict):
            cleaned["stations_count"] = stations_data.get("count", 0)
        else:
            cleaned["stations_count"] = 0

    return cleaned