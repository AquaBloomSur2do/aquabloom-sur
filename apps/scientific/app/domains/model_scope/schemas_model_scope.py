from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObservedRange(BaseModel):
    minimum: float = Field(allow_inf_nan=False)
    maximum: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_order(self) -> "ObservedRange":
        if self.minimum > self.maximum:
            raise ValueError("El mínimo observado no puede superar el máximo.")
        return self


class ModelScopeCreate(BaseModel):
    lake_id: UUID
    variable: str = Field(min_length=1, max_length=255)
    observed_range: ObservedRange
    experimental_condition: str = Field(min_length=1)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ModelScopeResponse(BaseModel):
    id: UUID
    lake_id: UUID
    variable: str
    observed_range: ObservedRange
    experimental_condition: str
    is_validated: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
