import json
import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from shapely.geometry import mapping
from shapely.wkt import loads as parse_wkt


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

    @field_validator("name", "region")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El campo no puede estar vacío o contener solo espacios.")
        return v


class LakeCreate(LakeBase):
    geom: dict[str, Any] = Field(
        ..., description="Geometría del lago en formato GeoJSON Polygon"
    )

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
                        raise ValueError(
                            f"No se pudo parsear la geometría WKT/JSON: {v}"
                        ) from None
            else:
                raise TypeError("La geometría debe ser un objeto JSON estructurado.")
        if v.get("type") != "Polygon":
            raise ValueError("La geometría debe ser estrictamente de tipo 'Polygon'.")
        coords = v.get("coordinates")
        if not coords or not isinstance(coords, list) or len(coords) == 0:
            raise ValueError("El polígono debe contener un arreglo de coordenadas válido.")
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
    def validate_geom(cls, v: dict[str, Any] | str | None) -> dict[str, Any] | None:
        if v is not None:
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
                            raise ValueError(
                                f"No se pudo parsear la geometría WKT/JSON: {v}"
                            ) from None
                else:
                    raise TypeError("La geometría debe ser un objeto JSON estructurado.")
            if v.get("type") != "Polygon":
                raise ValueError("La geometría debe ser un Polygon GeoJSON")
            if not v.get("coordinates"):
                raise ValueError("Las coordenadas no pueden estar vacías")
        return v


class LakeSummary(LakeBase):
    id: UUID
    status: str

    model_config = {"from_attributes": True}


class PaginatedLakes(BaseModel):
    items: list[LakeSummary]
    page: int
    page_size: int
    total: int


class LakeDetail(LakeSummary):
    geom: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @field_validator("geom", mode="before")
    @classmethod
    def parse_geom(cls, v: Any) -> dict[str, Any] | None:
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("{"):
                try:
                    return json.loads(v_str)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
            try:
                geom_obj = parse_wkt(v_str)
                return mapping(geom_obj)
            except (json.JSONDecodeError, TypeError, ValueError):
                raise ValueError(f"No se pudo parsear la geometría WKT/JSON: {v}") from None
        return v


class PaginatedLakes(BaseModel):
    items: list[LakeSummary]
    page: int
    page_size: int
    total: int


class MembershipCreate(BaseModel):
    profile_id: UUID = Field(..., description="ID del perfil del usuario")
    role: Literal["admin", "member"] = Field(..., description="Rol en la organización")


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


# --- Esquemas de Station ---


class CoordinatesUpdate(BaseModel):
    latitude: float = Field(
        ..., ge=-90.0, le=90.0, description="Latitud válida entre -90 y 90"
    )
    longitude: float = Field(
        ..., ge=-180.0, le=180.0, description="Longitud válida entre -180 y 180"
    )


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


class StationOut(BaseModel):
    id: UUID
    lake_id: UUID
    code: str
    name: str
    point: Any
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


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

