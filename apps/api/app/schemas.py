import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None


# --- Esquemas de Lake ---


class LakeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Nombre del lago")
    region: str = Field(
        ..., min_length=1, max_length=255, description="Región donde se ubica"
    )
    description: str | None = Field(None, description="Descripción opcional")


class LakeCreate(LakeBase):
    geom: dict[str, Any] = Field(
        ..., description="Geometría del lago en formato GeoJSON Polygon"
    )

    @field_validator("geom")
    @classmethod
    def validate_geom(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("type") != "Polygon":
            raise ValueError("La geometría debe ser un Polygon GeoJSON")
        if not v.get("coordinates"):
            raise ValueError("Las coordenadas no pueden estar vacías")
        return v


class LakeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    region: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    geom: dict[str, Any] | None = None
    status: str | None = Field(None, min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("El nombre del lago no puede estar vacío.")
        return v

    @field_validator("geom")
    @classmethod
    def validate_geom(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is not None:
            if v.get("type") != "Polygon":
                raise ValueError("La geometría debe ser un Polygon GeoJSON")
            if not v.get("coordinates"):
                raise ValueError("Las coordenadas no pueden estar vacías")
        return v


class LakeSummary(LakeBase):
    id: UUID
    status: str

    model_config = {"from_attributes": True}


class LakeDetail(LakeSummary):
    geom: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
class MembershipCreate(BaseModel):
    profile_id: UUID = Field(..., description="ID del perfil del usuario")
    role: Literal["admin", "member"] = Field(..., description="Rol en la organización")
    


# PaginatedLakes reubicado debajo de LakeSummary para evitar NameError
class PaginatedLakes(BaseModel):
    items: list[LakeSummary]
    page: int
    page_size: int
    total: int


# --- Esquemas de Station ---


class CoordinatesUpdate(BaseModel):
    latitude: float = Field(
        ..., ge=-90.0, le=90.0, description="Latitud válida entre -90 y 90"
    )
    longitude: float = Field(
        ..., ge=-180.0, le=180.0, description="Longitud válida entre -180 y 180"
    )


class StationUpdate(BaseModel):
    # Omitimos intencionalmente 'lake_id' y 'code' para que sea imposible sobrescribirlos
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


# --- Esquemas de Organization y Otros ---


class OrganizationCreate(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=255, description="Nombre de la organización"
    )
    identifier: str = Field(
        ..., min_length=1, max_length=100, description="Identificador único (slug)"
    )
    description: str | None = Field(None, description="Descripción opcional")

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9\-]+$", v):
            raise ValueError(
                "El identificador solo puede contener letras minúsculas, números y guiones."
            )
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
