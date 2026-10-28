from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    model_config = ConfigDict(
        json_schema_extra={
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
                }
            ]
        }
    )


class SpectralObservationResponse(SpectralObservationBase):
    id: UUID = Field(..., description="Identificador único de la observación en la base de datos")
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# CONTRATOS S2-111: Persistencia de Escenas
# ==========================================

class SceneBase(BaseModel):
    lake_id: UUID = Field(..., description="ID lógico del lago origen")
    scene_identifier: str = Field(..., description="Identificador único de la escena (ej. Sentinel-2 L2A...)")
    acquisition_date: date = Field(..., description="Fecha de adquisición de la escena")
    metadata: dict = Field(default_factory=dict, description="Metadatos en bruto de la escena")
    file_references: list[str] = Field(default_factory=list, description="Ubicaciones de archivos o capas TIFF")


class SceneCreate(SceneBase):
    pass


class SceneResponse(SceneBase):
    id: UUID = Field(..., description="ID único de la escena en la base de datos")
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

    