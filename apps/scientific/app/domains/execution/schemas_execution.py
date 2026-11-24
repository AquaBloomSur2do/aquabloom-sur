from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrainingConfig(BaseModel):
    dataset_id: UUID
    version_id: UUID
    epochs: int = Field(default=100, gt=0)
    learning_rate: float = Field(default=0.001, gt=0)


class ModelConfig(BaseModel):
    model_name: str
    version: str
    parameters: dict[str, Any] = {}


class InferencePoint(BaseModel):
    point_id: str
    latitude: float | None = None
    longitude: float | None = None
    features: dict[str, float] = Field(default_factory=dict)


class EstimationConfig(BaseModel):
    model_id: str
    scene_id: str
    points: list[InferencePoint] | None = None


class ScientificJobType(str, Enum):
    TRAINING = "training"
    MODELING = "modeling"
    ESTIMATION = "estimation"


class ScientificJobStatusEnum(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TrainingMetrics(BaseModel):
    mae: float = Field(ge=0.0)
    rmse: float = Field(ge=0.0)


class BaselineInfo(BaseModel):
    strategy: str = "mean_clorofila_a"
    target_variable: str = "clorofila_a"
    prediction_value: float
    train_sample_count: int = Field(ge=1)
    validation_sample_count: int = Field(ge=1)


class TrainingResult(BaseModel):
    model: str = "baseline"
    baseline: BaselineInfo
    prediction_value: float
    predictions: list[float]
    metrics: TrainingMetrics
    version: str | None = None
    dataset_version_id: str | None = None
    model_version_id: str | None = None
    status: ScientificJobStatusEnum = ScientificJobStatusEnum.COMPLETED
    warnings: list[str] = Field(default_factory=list)


class JobCreate(BaseModel):
    job_type: Literal["training", "modeling", "estimation"]
    config: TrainingConfig | ModelConfig | EstimationConfig

    @model_validator(mode="after")
    def validate_config_type(self) -> "JobCreate":
        if self.job_type == "training" and not isinstance(
            self.config, TrainingConfig
        ):
            raise ValueError(
                "La configuración debe ser TrainingConfig para trabajos 'training'"
            )
        if self.job_type == "modeling" and not isinstance(self.config, ModelConfig):
            raise ValueError(
                "La configuración debe ser ModelConfig para trabajos 'modeling'"
            )
        if self.job_type == "estimation" and not isinstance(
            self.config, EstimationConfig
        ):
            raise ValueError(
                "La configuración debe ser EstimationConfig para trabajos 'estimation'"
            )
        return self


class JobResponse(BaseModel):
    job_id: UUID
    status: str
    status_url: str
    message: str = "Job accepted and processing in background"

    model_config = ConfigDict(from_attributes=True)


class JobStatus(BaseModel):
    id: UUID = Field(alias="job_id")
    job_type: ScientificJobType
    status: ScientificJobStatusEnum
    config: dict[str, Any]
    result: TrainingResult | dict[str, Any] | None = None
    dataset_version_id: UUID | None = None
    model_version_id: UUID | None = None
    requested_by: UUID | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ModelScopeSpec(BaseModel):
    model_version_id: UUID
    lake_id: UUID
    target_variable: str = "chlorophyll_a"
    unit: str = "ug/L"
    required_index: str = "NDCI"
    min_index_value: float = -1.0
    max_index_value: float = 1.0
    status: str = "ACTIVE"

    model_config = ConfigDict(from_attributes=True)


class SpectralObservationInput(BaseModel):
    observation_id: UUID
    lake_id: UUID
    scene_id: UUID
    spectral_index: str
    index_value: float
    quality: str = "VALID"

    model_config = ConfigDict(from_attributes=True)


class EstimationRequestInput(BaseModel):
    lake_id: UUID
    scene_id: UUID
    target_variable: str = "chlorophyll_a"
    unit: str = "ug/L"
    required_index: str = "NDCI"
    observations: list[SpectralObservationInput] = Field(min_length=1)


class ValidatedEstimationInput(BaseModel):
    model_version_id: UUID
    lake_id: UUID
    scene_id: UUID
    target_variable: str
    unit: str
    required_index: str
    valid_observation_count: int
    warnings: list[str] = Field(default_factory=list)


class PilotMetricsResult(BaseModel):
    sample_count: int = Field(ge=1)
    mae: float = Field(ge=0.0)
    rmse: float = Field(ge=0.0)
    bias: float
    r2_computable: bool
    r2: float | None = None
    limitations: list[str] = Field(default_factory=list)
    