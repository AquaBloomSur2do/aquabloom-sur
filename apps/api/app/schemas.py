import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None

class LakeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Nombre del lago")
    region: str = Field(..., min_length=1, max_length=255, description="Región donde se ubica")
    description: str | None = Field(None, description="Descripción opcional")

class LakeCreate(LakeBase):
    geometry: dict = Field(..., description="Geometría del lago en formato GeoJSON")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("El nombre del lago no puede estar vacío.")
        return value.strip()

    @field_validator("geometry")
    @classmethod
    def validate_geometry_format(cls, value: dict) -> dict:
        if not isinstance(value, dict) or "type" not in value:
            raise ValueError("Geometría inválida. Se requiere un formato GeoJSON válido con el atributo 'type'.")
        return value

class LakeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    region: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    geometry: dict | None = None
    status: str | None = Field(None, min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("El nombre del lago no puede estar vacío.")
        return v

    @field_validator("geometry")
    @classmethod
    def validate_geometry(cls, v: dict | None) -> dict | None:
        if v is not None and (not isinstance(v, dict) or "type" not in v):
            raise ValueError("Geometría inválida. Se requiere un formato GeoJSON válido con el atributo 'type'.")
        return v

class LakeSummary(LakeBase):
    id: UUID
    status: str
    model_config = {"from_attributes": True}

class LakeDetail(LakeSummary):
    geometry: dict
    created_at: datetime
    updated_at: datetime

class PaginatedLakes(BaseModel):
    items: list[LakeSummary]
    page: int
    page_size: int
    total: int

class CoordinatesUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitud válida entre -90 y 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitud válida entre -180 y 180")

class StationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    coordinates: CoordinatesUpdate | None = None
    status: str | None = Field(None, min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("El nombre de la estación no puede ser una cadena vacía.")
        return v

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Nombre de la organización")
    identifier: str = Field(..., min_length=1, max_length=100, description="Identificador único (slug)")
    description: str | None = Field(None, description="Descripción opcional")

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9\-]+$", v):
            raise ValueError("El identificador solo puede contener letras minúsculas, números y guiones.")
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
    geometry: dict | None
    properties: dict

class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]
    