from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ScientificJobType(str, Enum):
    TRAINING = "training"
    MODELING = "modeling"
    ESTIMATION = "estimation"


class ScientificJobStatusEnum(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreate(BaseModel):
    job_type: Literal["training", "modeling", "estimation"]
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
    status: str
    status_url: str
    message: str = "Job accepted and processing in background"
    
    model_config = ConfigDict(from_attributes=True)


class JobStatus(BaseModel):
    id: UUID = Field(alias="job_id")  # Alias para mantener retrocompatibilidad con clientes existentes
    job_type: ScientificJobType
    status: ScientificJobStatusEnum
    config: dict[str, Any]
    result: dict[str, Any] | None = None
    dataset_version_id: UUID | None = None
    model_version_id: UUID | None = None
    requested_by: UUID | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)