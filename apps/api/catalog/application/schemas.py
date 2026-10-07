from enum import Enum
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, Field


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


# ==========================================
# CONTRATOS S2-102: Observaciones Espectrales
# ==========================================

class QualityEnum(str, Enum):
    OPTIMA = "OPTIMA"
    ACEPTABLE = "ACEPTABLE"
    RECHAZADA = "RECHAZADA"


class SpectralObservationBase(BaseModel):
    scene_id: UUID = Field(..., description="Identificador único de la escena de origen (Ref: S2-101)")
    sample_id: UUID = Field(..., description="Referencia al identificador de la muestra in-situ")
    bands: dict[str, float] = Field(..., description="Valores por banda espectral (ej. {'B04': 0.12, 'B08': 0.45})")
    spectral_index: str = Field(..., description="Nombre del índice espectral calculado (ej. 'NDVI', 'NDWI')")
    index_value: float = Field(..., description="Valor numérico resultante del índice")
    unit: str = Field(..., description="Unidad de medida (ej. 'reflectancia', 'adimensional')")
    quality: QualityEnum = Field(..., description="Bandera de calidad de la observación espectral")


class SpectralObservationCreate(SpectralObservationBase):
    class Config:
        json_schema_extra: ClassVar[dict] = {
            "examples": [
                {
                    "summary": "Caso Válido (Óptimo)",
                    "description": "Observación espectral con cielo despejado y valores normales.",
                    "value": {
                        "scene_id": "123e4567-e89b-12d3-a456-426614174000",
                        "sample_id": "987e6543-e21b-34d3-b456-426614174011",
                        "bands": {"B04": 0.15, "B08": 0.65},
                        "spectral_index": "NDVI",
                        "index_value": 0.625,
                        "unit": "adimensional",
                        "quality": "OPTIMA"
                    }
                },
                {
                    "summary": "Caso Rechazado (Saturación/Nubes)",
                    "description": "Observación descartada por valores anómalos o cobertura nubosa.",
                    "value": {
                        "scene_id": "123e4567-e89b-12d3-a456-426614174000",
                        "sample_id": "987e6543-e21b-34d3-b456-426614174011",
                        "bands": {"B04": 1.0, "B08": 1.0},
                        "spectral_index": "NDVI",
                        "index_value": 0.0,
                        "unit": "adimensional",
                        "quality": "RECHAZADA"
                    }
                }
            ]
        }


class SpectralObservationResponse(SpectralObservationBase):
    id: UUID = Field(..., description="Identificador único de la observación en la base de datos")

    class Config:
        from_attributes = True

