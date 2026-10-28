import json
import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from shapely.geometry import mapping
from shapely.wkt import loads as parse_wkt

# --- Ciclo de Vida y Estados de Versión de Dataset (S2-134) ---


class VersionState(str, Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DatasetVersionStateUpdate(BaseModel):
    state: VersionState = Field(
        ..., description="Nuevo estado del ciclo de vida de la versión"
    )


# --- Observaciones Espectrales ---


class QualityEnum(str, Enum):
    OPTIMA = "OPTIMA"
    ACEPTABLE = "ACEPTABLE"
    RECHAZADA = "RECHAZADA"


class SpectralObservationBase(BaseModel):
    scene_id: UUID = Field(..., description="Identificador único de la escena de origen")
    sample_id: UUID = Field(..., description="Referencia a la muestra in-situ")
    bands: dict[str, float] = Field(..., description="Valores por banda espectral")
    spectral_index: str = Field(..., description="Nombre del índice espectral (ej. NDCI)")
    index_value: float = Field(..., description="Valor resultante del índice")
    unit: str = Field(..., description="Unidad de medida")
    quality: QualityEnum = Field(..., description="Calidad de la observación")


class SpectralObservationCreate(SpectralObservationBase):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "Caso Válido (NDCI Óptimo)",
                    "value": {
                        "scene_id": "123e4567-e89b-12d3-a456-426614174000",
                        "sample_id": "987e6543-e21b-34d3-b456-426614174011",
                        "bands": {"B04": 0.10, "B05": 0.30},
                        "spectral_index": "NDCI",
                        "index_value": 0.5,
                        "unit": "adimensional",
                        "quality": "OPTIMA",
                    },
                }
            ]
        }
    )


class SpectralObservationResponse(SpectralObservationBase):
    id: UUID = Field(..., description="ID de la observación")

    model_config = ConfigDict(from_attributes=True)


class NdciObservationSchema(BaseModel):
    lake_id: str | None = Field(default=None)
    ndci_value: float | None = Field(default=None)
    observation: str | None = Field(default=None)


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None


class DashboardSummaryResponse(BaseModel):
    active_lakes_count: int
    active_stations_count: int
    visible_organizations_count: int


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

    model_config = {"from_attributes": True}


class LakeDetail(LakeSummary):
    geom: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PaginatedLakes(BaseModel):
    items: list[LakeSummary]
    page: int
    page_size: int
    total: int


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


class SceneDetail(BaseModel):
    id: str
    procedencia: str
    checksum: str
    calidad: str


class MembershipCreate(BaseModel):
    profile_id: UUID
    role: Literal["admin", "member"]


class UserOrganizationResponse(BaseModel):
    id: UUID
    name: str
    role: str


class OrganizationMemberResponse(BaseModel):
    user_id: UUID
    profile_id: UUID | None = None
    full_name: str | None = None
    email: str | None = None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class ProfileOption(BaseModel):
    id: UUID
    email: str | None = None
    name: str | None = None


class CoordinatesUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class StationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    coordinates: CoordinatesUpdate | None = None
    status: str | None = Field(None, min_length=1, max_length=50)


class GeoJSONPoint(BaseModel):
    type: Literal["Point"]
    coordinates: tuple[float, float]


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


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    identifier: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9\-]+$", v):
            raise ValueError("El identificador solo admite minúsculas, números y guiones.")
        return v


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    identifier: str
    description: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any] | None
    properties: dict[str, Any]


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]
    