from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    file_paths: list[str] = Field(..., description="Listado exacto de los archivos incluidos")
    checksum: str = Field(..., description="Hash de validación de integridad (ej. SHA-256)")


class DatasetManifestResponse(DatasetManifestBase):
    id: UUID
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    
