import hashlib
import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel

from app.database import supabase
from app.dependencies import require_internal_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])
MODEL_ARTIFACT_BUCKET = "model_artifacts"
MAX_MODEL_ARTIFACT_SIZE = 100 * 1024 * 1024
ARTIFACT_READ_CHUNK_SIZE = 1024 * 1024


class ModelArtifactResponse(BaseModel):
    id: UUID
    training_job_id: UUID
    filename: str
    content_type: str
    file_size: int
    checksum: str
    storage_path: str
    created_at: datetime


def _require_database():
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de base de datos no disponible.",
        )
    return supabase


async def _read_artifact(file: UploadFile) -> tuple[bytes, str]:
    content = bytearray()
    checksum = hashlib.sha256()
    while chunk := await file.read(ARTIFACT_READ_CHUNK_SIZE):
        if len(content) + len(chunk) > MAX_MODEL_ARTIFACT_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=(
                    "El artefacto supera el límite de "
                    f"{MAX_MODEL_ARTIFACT_SIZE // (1024 * 1024)} MiB."
                ),
            )
        content.extend(chunk)
        checksum.update(chunk)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de artefacto está vacío.",
        )
    return bytes(content), checksum.hexdigest()


def _find_training_job(client, job_id: UUID) -> dict:
    response = (
        client.table("scientific_jobs")
        .select("id, job_type")
        .eq("id", str(job_id))
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el trabajo de entrenamiento.",
        )
    job = response.data[0]
    if job.get("job_type") != "training":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se pueden asociar artefactos a trabajos de entrenamiento.",
        )
    return job


@router.post(
    "/{job_id}/artifact",
    response_model=ModelArtifactResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_internal_service)],
)
async def save_model_artifact(
    job_id: UUID,
    response: Response,
    file: Annotated[UploadFile, File(...)],
):
    client = _require_database()
    _find_training_job(client, job_id)
    content, checksum = await _read_artifact(file)

    existing_response = (
        client.table("model_artifacts")
        .select("*")
        .eq("training_job_id", str(job_id))
        .limit(1)
        .execute()
    )
    if existing_response.data:
        existing = existing_response.data[0]
        if existing["checksum"] != checksum:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El trabajo de entrenamiento ya tiene otro artefacto.",
            )
        response.status_code = status.HTTP_200_OK
        return existing

    filename = (file.filename or "model-artifact").replace("\\", "/").rsplit("/", 1)[-1]
    filename = filename.replace("\x00", "") or "model-artifact"
    content_type = file.content_type or "application/octet-stream"
    storage_path = f"{job_id}/{checksum}"

    try:
        client.storage.from_(MODEL_ARTIFACT_BUCKET).upload(
            storage_path,
            content,
            file_options={
                "content-type": content_type,
                "upsert": "false",
            },
        )
    except Exception as exc:
        logger.exception("No se pudo subir el artefacto del trabajo %s.", job_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo almacenar el artefacto del modelo.",
        ) from exc

    try:
        database_response = (
            client.table("model_artifacts")
            .insert(
                {
                    "training_job_id": str(job_id),
                    "filename": filename,
                    "content_type": content_type,
                    "file_size": len(content),
                    "checksum": checksum,
                    "storage_path": storage_path,
                }
            )
            .execute()
        )
    except Exception as exc:
        try:
            client.storage.from_(MODEL_ARTIFACT_BUCKET).remove([storage_path])
        except Exception:
            logger.exception(
                "No se pudo limpiar el artefacto huérfano %s tras fallar PostgreSQL.",
                storage_path,
            )
        logger.exception("No se pudo registrar el artefacto del trabajo %s.", job_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo registrar el artefacto del modelo.",
        ) from exc

    if not database_response.data:
        try:
            client.storage.from_(MODEL_ARTIFACT_BUCKET).remove([storage_path])
        except Exception:
            logger.exception(
                "No se pudo limpiar el artefacto huérfano %s tras una inserción vacía.",
                storage_path,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se devolvieron los datos del artefacto registrado.",
        )
    return database_response.data[0]


@router.get(
    "/{job_id}/artifact",
    response_model=ModelArtifactResponse,
    dependencies=[Depends(require_internal_service)],
)
def get_model_artifact(job_id: UUID):
    client = _require_database()
    _find_training_job(client, job_id)
    artifact_response = (
        client.table("model_artifacts")
        .select("*")
        .eq("training_job_id", str(job_id))
        .limit(1)
        .execute()
    )
    if not artifact_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El trabajo todavía no tiene un artefacto de modelo.",
        )
    return artifact_response.data[0]
