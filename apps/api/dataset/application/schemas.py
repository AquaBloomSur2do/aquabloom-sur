from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CandidateState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VersionState(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DatasetCandidateBase(BaseModel):
    lake_id: UUID = Field(..., description="Identificador del lago origen")
    data_uri: str = Field(..., description="Ruta de almacenamiento del dataset candidato (ej. s3://...)")
    status: CandidateState = Field(default=CandidateState.PENDING, description="Estado actual del candidato")


class DatasetCandidateResponse(DatasetCandidateBase):
    id: UUID
    submitted_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DatasetDecisionCreate(BaseModel):
    candidate_id: UUID = Field(..., description="ID del candidato a evaluar")
    decision: CandidateState = Field(..., description="Resolución estricta (APPROVED o REJECTED)")
    comments: str | None = Field(None, description="Justificación técnica de la evaluación")


class DatasetVersionBase(BaseModel):
    tag: str = Field(..., description="Etiqueta semántica de versión (ej. v1.0.0)")
    status: VersionState = Field(default=VersionState.DRAFT, description="Estado del ciclo de vida")
    changelog: str = Field(..., description="Registro detallado de modificaciones")


class DatasetVersionResponse(DatasetVersionBase):
    id: UUID
    published_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class DatasetManifestBase(BaseModel):
    version_id: UUID = Field(..., description="ID de la versión consolidada")
    file_paths: list[str] = Field(..., min_length=1, max_length=50, description="Listado exacto de los archivos incluidos")
    checksum: str = Field(..., description="Hash de validación de integridad (ej. SHA-256)")


class DatasetManifestResponse(DatasetManifestBase):
    id: UUID
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CandidateVariableMetadata(BaseModel):
    variable: str = Field(..., description="Nombre de la variable (ej. temperatura)")
    unit: str = Field(..., description="Unidad de medida")

    @model_validator(mode="after")
    def validate_variable_and_unit(self) -> "CandidateVariableMetadata":
        # Diccionario estricto de variables permitidas y sus unidades compatibles para AquaBloom Sur
        valid_combinations = {
            "temperatura": ["celsius", "°c", "c"],
            "clorofila_a": ["mg/m3", "ug/l", "µg/l"],
            "turbidez": ["ntu"],
            "ph": ["adimensional"],
        }

        var_clean = self.variable.lower().strip()
        unit_clean = self.unit.lower().strip()

        if var_clean not in valid_combinations:
            raise ValueError(
                f"Variable incompatible o no soportada por el sistema: '{self.variable}'"
            )

        if unit_clean not in valid_combinations[var_clean]:
            raise ValueError(
                f"Unidad '{self.unit}' es incompatible para la variable '{self.variable}'. "
                f"Unidades permitidas: {valid_combinations[var_clean]}"
            )

        return self


class CandidateValidationPayload(BaseModel):
    candidate_id: UUID
    acquisition_date: datetime = Field(
        ..., description="Fecha y hora de adquisición de los datos"
    )
    variables: list[CandidateVariableMetadata] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Lista de variables reportadas por el candidato",
    )

    @field_validator("acquisition_date")
    @classmethod
    def validate_date_not_in_future(cls, v: datetime) -> datetime:
        # Asignamos zona horaria UTC si viene sin una para poder comparar correctamente
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)

        # Rechazamos fechas que vengan del futuro
        if v > datetime.now(UTC):
            raise ValueError(
                f"La fecha de adquisición ({v}) es incompatible: no puede estar en el futuro."
            )

        return v


class IncorporateCandidatesInput(BaseModel):
    candidate_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Lista de IDs de candidatos a incorporar desde la ingesta",
    )

class TrainingManifestResponse(BaseModel):
    version_id: UUID
    manifest_id: UUID
    variables: list[str] = Field(..., max_length=50)
    checksum: str
    download_url: str
    manifest_version: str = "1.0.0"
    sources: list[str] = Field(default_factory=list, max_length=50)
    is_experimental: bool = False
    is_synthetic: bool = False

    model_config = ConfigDict(from_attributes=True)
    