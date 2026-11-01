from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TrainingConfig(BaseModel):
    dataset_id: str
    epochs: int = Field(default=100, gt=0)
    learning_rate: float = Field(default=0.001, gt=0)


class ModelConfig(BaseModel):
    model_name: str
    version: str
    parameters: dict[str, Any] = {}


class EstimationConfig(BaseModel):
    model_id: str
    scene_id: str


class JobCreate(BaseModel):
    job_type: Literal["training", "modeling", "estimation"]
    organization_id: UUID
    config: TrainingConfig | ModelConfig | EstimationConfig

    @model_validator(mode="after")
    def validate_config_type(self) -> "JobCreate":
        if self.job_type == "training" and not isinstance(self.config, TrainingConfig):
            raise ValueError("La configuración debe ser TrainingConfig para trabajos 'training'")
        if self.job_type == "modeling" and not isinstance(self.config, ModelConfig):
            raise ValueError("La configuración debe ser ModelConfig para trabajos 'modeling'")
        if self.job_type == "estimation" and not isinstance(self.config, EstimationConfig):
            raise ValueError("La configuración debe ser EstimationConfig para trabajos 'estimation'")
        return self


class JobResponse(BaseModel):
    job_id: UUID
    status: Literal["pending", "running", "completed", "failed"]
    status_url: str
    message: str = "Job accepted and processing in background"


class JobStatus(BaseModel):
    job_id: UUID
    status: Literal["pending", "running", "completed", "failed"] = Field(
        description="Estado actual: pending, running, completed o failed."
    )
    result: dict[str, Any] | None = None
    created_at: datetime
    