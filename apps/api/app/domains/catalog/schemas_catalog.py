import json
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry import mapping
from shapely.wkt import loads as parse_wkt


# --- Esquemas de Lake ---


class LakeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    region: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None)

    @field_validator("name", "region")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El campo no puede estar vacío.")
        return v


class LakeCreate(LakeBase):
    geom: dict[str, Any] = Field(..., description="Geometría GeoJSON Polygon")

    @field_validator("geom")
    @classmethod
    def validate_geom(cls, v: dict[str, Any] | str) -> dict[str, Any]:
        if not isinstance(v, dict):
            if isinstance(v, str):
                v_str = v.strip()
                if v_str.startswith("{"):
                    try:
                        v = json.loads(v_str)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                if isinstance(v, str):
                    try:
                        v = mapping(parse_wkt(v_str))
                    except (json.JSONDecodeError, TypeError, ValueError):
                        raise ValueError(f"No se pudo parsear la geometría: {v}") from None
            else:
                raise TypeError("La geometría debe ser un objeto JSON estructurado.")
        if v.get("type") != "Polygon":
            raise ValueError("La geometría debe ser un Polygon GeoJSON.")
        return v


class LakeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    region: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    geom: dict[str, Any] | None = None
    status: str | None = Field(None, min_length=1, max_length=50)


class LakeSummary(LakeBase):
    id: UUID
    status: str
    stations_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class LakeDetail(LakeSummary):
    geom: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PaginatedLakes(BaseModel):
    items: list[LakeSummary]
    page: int
    page_size: int
    total: int


# --- Esquemas de Station ---


class CoordinatesUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class GeoJsonPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float] | tuple[float, float] = Field(
        ..., description="Coordenadas en formato [longitud, latitud]"
    )


# Alias para mantener compatibilidad con tests o imports que usen GeoJSONPoint
GeoJSONPoint = GeoJsonPoint


class StationBase(BaseModel):
    code: str = Field(..., description="Código único de la estación")
    name: str = Field(..., description="Nombre de la estación")
    status: str = Field(
        "active", description="Estado de la estación (active, inactive)"
    )
    source: str = Field(..., description="Fuente de la estación (ej. DGA)")
    activity: str = Field(..., description="Actividad de la estación")
    point: GeoJsonPoint = Field(..., description="Geometría GeoJSON Point [lon, lat]")


class StationCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    description: str | None = None
    status: str | None = "active"


class StationUpdate(BaseModel):
    code: str | None = None
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    coordinates: CoordinatesUpdate | None = None
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    source: str | None = None
    activity: str | None = None
    status: str | None = Field(None, min_length=1, max_length=50)


class StationResponse(StationBase):
    id: UUID = Field(..., description="ID único de la estación")
    lake_id: UUID

    model_config = ConfigDict(from_attributes=True)


class StationOut(BaseModel):
    id: UUID
    lake_id: UUID
    code: str
    name: str
    point: GeoJSONPoint
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


# --- Esquemas GeoJSON y Escenas por Lago ---


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any] | None
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]


class SceneOut(BaseModel):
    id: UUID
    lake_id: UUID
    scene_identifier: str
    acquisition_date: date
    created_at: datetime


class PaginatedScenes(BaseModel):
    items: list[SceneOut]
    page: int
    page_size: int
    total: int
