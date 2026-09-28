from uuid import UUID

from pydantic import BaseModel, Field


class StationBase(BaseModel):
    code: str = Field(..., description="Código único de la estación")
    name: str = Field(..., description="Nombre de la estación")
    latitude: float = Field(
        ..., 
        ge=-90.0, 
        le=90.0, 
        description="Latitud entre -90 y 90"
    )
    longitude: float = Field(
        ..., 
        ge=-180.0, 
        le=180.0, 
        description="Longitud entre -180 y 180"
    )
    source: str = Field(..., description="Fuente de la estación (ej. DGA)")
    activity: str = Field(..., description="Actividad de la estación")

class StationCreate(StationBase):
    lake_id: UUID

class StationUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)
    source: str | None = None
    activity: str | None = None

class StationSummary(BaseModel):
    station_id: UUID
    code: str
    name: str
    lake_id: UUID

class StationDetail(StationBase):
    station_id: UUID
    lake_id: UUID
 