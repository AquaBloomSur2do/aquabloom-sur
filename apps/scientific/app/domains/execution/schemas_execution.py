import math
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    point_id: str = Field(min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    features: dict[str, float] = Field(default_factory=dict)

    @field_validator("point_id")
    @classmethod
    def normalize_point_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("point_id no puede estar vacío.")
        return normalized

    @field_validator("features")
    @classmethod
    def validate_finite_features(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not math.isfinite(feature) for feature in value.values()):
            raise ValueError("features debe contener solo valores finitos.")
        return value


class EstimationConfig(BaseModel):
    model_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    points: list[InferencePoint] | None = Field(default=None, min_length=1)
    model_name: str | None = None
    model_version_id: UUID | None = None
    training_job_id: UUID | None = None
    dataset_id: UUID | None = None
    dataset_version_id: UUID | None = None

    @field_validator("model_id", "scene_id", mode="before")
    @classmethod
    def normalize_required_ids(cls, value: Any) -> str:
        if isinstance(value, UUID):
            return str(value)
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("El identificador no puede estar vacío.")
        return normalized


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


class TrainingPartitionMetadata(BaseModel):
    strategy: Literal["sequential"]
    split_ratio: float = Field(gt=0, lt=1)
    train_sample_count: int = Field(ge=1)
    validation_sample_count: int = Field(ge=1)


class ReproducibilityMetadata(BaseModel):
    dataset_version_id: str
    partition: TrainingPartitionMetadata
    seed: int | None
    configuration: dict[str, Any]
    code_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)


class ProvenanceSource(BaseModel):
    id: str
    source_name: str | None = None
    checksum: str
    is_synthetic: bool = False
    is_experimental: bool = False


class DatasetProvenanceInfo(BaseModel):
    dataset_id: str
    version_id: str
    version_number: str
    manifest_checksum: str
    origin: Literal["synthetic", "real", "mixed", "unknown"]
    sources: list[ProvenanceSource] = Field(default_factory=list)
    pilot_fixture: dict[str, Any] | None = None


class TrainingResult(BaseModel):
    model: str = "baseline"
    baseline: BaselineInfo
    prediction_value: float
    predictions: list[float]
    metrics: TrainingMetrics
    version: str | None = None
    dataset_version_id: str | None = None
    model_version_id: str | None = None
    reproducibility: ReproducibilityMetadata | None = None
    status: ScientificJobStatusEnum = ScientificJobStatusEnum.COMPLETED
    warnings: list[str] = Field(default_factory=list)
    provenance: DatasetProvenanceInfo | None = None
    limitations: list[str] = Field(default_factory=list)


class TraceabilityEvidence(BaseModel):
    job_id: UUID
    scene_id: UUID
    dataset_version_id: UUID
    model_id: str = Field(min_length=1)
    processing_id: UUID


class JobCreate(BaseModel):
    job_type: Literal["training", "modeling", "estimation"]
    config: TrainingConfig | ModelConfig | EstimationConfig

    @model_validator(mode="after")
    def validate_config_type(self) -> "JobCreate":
        if self.job_type == "training" and not isinstance(self.config, TrainingConfig):
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
    traceability_evidence: TraceabilityEvidence | None = None
    dataset_version_id: UUID | None = None
    model_version_id: UUID | None = None
    scene_id: UUID | None = None
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

class ModelArtifactAccess(BaseModel):
    job_id: UUID
    download_url: str
    expires_in: int = Field(gt=0)
    checksum: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
