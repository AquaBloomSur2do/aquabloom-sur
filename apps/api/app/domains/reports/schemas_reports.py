from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ResourceReportCreate(BaseModel):
    resource_type: Literal["lake", "station"]
    resource_id: UUID
    reason: str = Field(..., min_length=1, max_length=2000)
    details: str | None = Field(None, max_length=5000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El motivo del reporte no puede estar vacío.")
        return normalized

    @field_validator("details")
    @classmethod
    def normalize_details(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ResourceReportResolution(BaseModel):
    resolution_reason: str = Field(..., min_length=1, max_length=2000)

    @field_validator("resolution_reason")
    @classmethod
    def validate_resolution_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("El motivo de resolución no puede estar vacío.")
        return normalized


class ResourceReportResponse(BaseModel):
    id: UUID
    resource_type: Literal["lake", "station"]
    resource_id: UUID
    reported_by: UUID
    reason: str
    details: str | None = None
    status: Literal["open", "resolved"]
    resolution_reason: str | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
