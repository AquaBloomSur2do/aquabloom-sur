from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None


# --- Esquemas de Lake ---

class LakeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Nombre del lago")
    region: str = Field(..., min_length=1, max_length=255, description="Región donde se ubica")
    description: str | None = Field(None, description="Descripción opcional")


class LakeCreate(LakeBase):
    geom: dict[str, Any] = Field(..., description="Geometría del lago en formato GeoJSON Polygon")

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
    
