from typing import Any

from app.schemas import GeoJSONFeature, GeoJSONFeatureCollection


def to_geojson_feature_collection(data: list[dict[str, Any]], geom_key: str = "geom") -> GeoJSONFeatureCollection:
    features = []
    
    for item in data:
        record = item.copy()
        # Extraemos la geometría del registro original
        geometry = record.pop(geom_key, None)
        
        # El resto de los datos se convierten en las propiedades
        features.append(
            GeoJSONFeature(
                type="Feature",
                geometry=geometry,
                properties=record
            )
        )
        
    return GeoJSONFeatureCollection(
        type="FeatureCollection",
        features=features
    )

