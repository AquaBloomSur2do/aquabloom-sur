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
    result: dict[str, Any] = Field(min_length=1)
    rules: list[AppliedRule] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class PredictionResponse(PredictionCreate):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(extra="forbid", from_attributes=True)
