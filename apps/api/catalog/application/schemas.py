from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class GeoJsonPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(
        ..., description="Coordenadas en formato [longitud, latitud]"
    )


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
    name: str | None = None
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    source: str | None = None
    activity: str | None = None
    status: str | None = None


class StationResponse(StationBase):
    id: UUID = Field(..., description="ID único de la estación")
    lake_id: UUID

    class Config:
        from_attributes = True

class ImportCreate(BaseModel):
    station_id: UUID = Field(..., description="ID de la estación asociada")
    srid: int = Field(..., description="Spatial Reference System Identifier")
    chlorophyll_a: float = Field(..., description="Nivel de clorofila-a en mg/L")
    sample_date: str = Field(..., description="Fecha de la muestra")

    @field_validator('srid')
    @classmethod
    def validate_srid(cls, value):
        if value != 4326:
            raise ValueError("El SRID debe ser estrictamente 4326 (WGS 84)")
        return value

    @field_validator('chlorophyll_a')
    @classmethod
    def validate_units(cls, value):
        if value < 0:
            raise ValueError("El valor de clorofila-a no puede ser negativo")
        return value
    