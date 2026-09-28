from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field


class GeoJsonPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(..., description="Coordenadas en formato [longitud, latitud]")


class StationBase(BaseModel):
    code: str = Field(..., description="Código único de la estación")
    name: str = Field(..., description="Nombre de la estación")
    status: str = Field("active", description="Estado de la estación (active, inactive)")
    source: str = Field(..., description="Fuente de la estación (ej. DGA)")
    activity: str = Field(..., description="Actividad de la estación")
    point: GeoJsonPoint = Field(..., description="Geometría GeoJSON Point [lon, lat]")


class StationCreate(BaseModel):
    code: str
    name: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    source: str
    activity: str
    status: Optional[str] = "active"
    lake_id: UUID


class StationUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    source: Optional[str] = None
    activity: Optional[str] = None
    status: Optional[str] = None


class StationResponse(StationBase):
    id: UUID = Field(..., description="ID único de la estación")
    lake_id: UUID

    class Config:
        from_attributes = True
                