from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AppliedRule(BaseModel):
    rule_id: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class PredictionCreate(BaseModel):
    model_version_id: UUID
    scene_id: UUID
    organization_id: UUID | None = None
    result: dict[str, Any] = Field(min_length=1)
    rules: list[AppliedRule] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class PredictionResponse(PredictionCreate):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class EstimationPoint(BaseModel):
    point_id: str | None = None
    station_id: UUID | str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    value: float = Field(allow_inf_nan=False)
    label: str | None = None
    quality: str | None = None

    model_config = ConfigDict(extra="forbid")


class EstimationProvenance(BaseModel):
    model_version_id: UUID
    scene_id: UUID
    lake_id: UUID | None = None
    scene_identifier: str | None = None
    acquisition_date: str | None = None
    dataset_version_id: UUID | None = None
    rules: list[AppliedRule] = Field(default_factory=list)
    generated_at: datetime

    model_config = ConfigDict(extra="forbid")


class PredictionDetailResponse(BaseModel):
    id: UUID
    organization_id: UUID
    variable: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    status: str = Field(min_length=1)
    points: list[EstimationPoint] = Field(default_factory=list)
    provenance: EstimationProvenance
    warnings: list[str] = Field(default_factory=list)
    usage_limits: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(extra="forbid")


