from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ImportResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str | None
    checksum: str
    file_size: int
    status: str
    created_at: datetime


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
    @classmethod
    def validate_srid(cls, v: int) -> int:
        if v != 4326:
            raise ValueError("El SRID debe ser exactamente 4326")
        return v

    @field_validator("chlorophyll_a")
    @classmethod
    def validate_chlorophyll(cls, v: float) -> float:
        if v < 0:
            raise ValueError("chlorophyll_a no puede ser negativo")
        return v


class SampleResponse(BaseModel):
    id: UUID = Field(..., description="Identificador interno de la muestra")
    station_id: UUID = Field(..., description="Estación donde se tomó la muestra")
    sample_datetime_utc: datetime = Field(..., description="Fecha y hora en UTC")
    chlorophyll_a_ug_l: float = Field(..., description="Concentración de clorofila-a")
    is_quarantined: bool = Field(
        ..., description="Indica si la muestra está en cuarentena"
    )
    quarantine_reason: str | None = Field(
        None, description="Motivo de la cuarentena si aplica"
    )


class SampleListResponse(BaseModel):
    items: list[SampleResponse]
    total: int
    page: int
    page_size: int
