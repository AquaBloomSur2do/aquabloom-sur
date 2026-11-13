from typing import Any
from uuid import UUID

from apps.api.app.core.permissions import CATALOG_ACTIONS, has_permission
from apps.api.app.domains.catalog.model_catalog import (
    get_lake_by_id as get_active_lake_by_id,
)
from apps.api.app.domains.catalog.model_catalog import (
    soft_delete_lake,
)
from apps.api.app.domains.catalog.schemas_catalog import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
)


def to_geojson_feature_collection(
    data: list[dict[str, Any]], geom_key: str = "geom"
) -> GeoJSONFeatureCollection:
    features = []

    for item in data:
        record = item.copy()
        geometry = record.pop(geom_key, None)
        features.append(
            GeoJSONFeature(type="Feature", geometry=geometry, properties=record)
        )

    return GeoJSONFeatureCollection(type="FeatureCollection", features=features)


def get_lake_by_id(supabase, lake_id: UUID) -> dict:
    return get_active_lake_by_id(supabase, lake_id)


def disable_lake(
    lake_id: UUID, current_user: dict | None = None, supabase=None
) -> dict:
    if not has_permission(current_user, CATALOG_ACTIONS["DISABLE"]):
        raise PermissionError("No tienes permisos para desactivar lagos.")

    if supabase is None:
        raise ValueError(
            "La conexión a la base de datos es requerida para desactivar un lago."
        )

    try:
        return soft_delete_lake(supabase, lake_id)
    except LookupError as exc:
        raise LookupError("Lago no encontrado") from exc
