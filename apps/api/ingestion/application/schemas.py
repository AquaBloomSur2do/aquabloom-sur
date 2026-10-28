from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PreparedInputCreate(BaseModel):
    original_import_id: UUID
    source_key: str = Field(..., min_length=1, max_length=255)
    metadata: dict[str, Any]

    @field_validator("source_key", mode="before")
    @classmethod
    def normalize_source_key(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class PreparedInputResponse(BaseModel):
    id: UUID
    original_import_id: UUID
    source_key: str
    metadata: dict[str, Any]
    created_at: datetime


class ImportCreate(BaseModel):
    srid: int
    chlorophyll_a: float

    @field_validator("srid")
    def validate_srid(cls, v):
        if v != 4326:
            raise ValueError("El SRID debe ser exactamente 4326")
        return v
        
    @field_validator("chlorophyll_a")
    def validate_chlorophyll(cls, v):
        if v < 0:
            raise ValueError("chlorophyll_a no puede ser negativo")
        return v
    