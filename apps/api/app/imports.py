import hashlib
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from postgrest.exceptions import APIError
from pydantic import BaseModel

from app.auth import verify_supabase_jwt
from app.database import supabase

router = APIRouter(prefix="/api/v1/imports", tags=["Imports"])


class ImportResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str | None
    checksum: str
    file_size: int
    status: str
    created_at: datetime


def _find_import(*, idempotency_key: str | None, checksum: str) -> dict | None:
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    if idempotency_key:
        response = (
            supabase.table("imports")
            .select("*")
            .eq("idempotency_key", idempotency_key)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]

    response = (
        supabase.table("imports")
        .select("*")
        .eq("checksum", checksum)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def _check_idempotency_key(record: dict, checksum: str) -> dict:
    if record["checksum"] != checksum:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La clave de idempotencia ya fue usada con otro archivo.",
        )
    return record


@router.post("", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def create_import(
    file: Annotated[UploadFile, File(...)],
    api_response: Response,
    _user: Annotated[dict, Depends(verify_supabase_jwt)],
    idempotency_key: Annotated[
        str | None, Header(alias="X-Idempotency-Key", max_length=255)
    ] = None,
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    idempotency_key = idempotency_key.strip() if idempotency_key else None
    if idempotency_key == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de importación está vacío.",
        )

    checksum = hashlib.sha256(content).hexdigest()
    existing = _find_import(idempotency_key=idempotency_key, checksum=checksum)
    if existing:
        api_response.status_code = status.HTTP_200_OK
        return _check_idempotency_key(existing, checksum)

    filename = (file.filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    if not filename:
        filename = "upload"
    content_type = file.content_type
    storage_path = checksum

    try:
        supabase.storage.from_("imports").upload(
            storage_path,
            content,
            file_options={
                "content-type": content_type or "application/octet-stream",
                "upsert": "true",
            },
        )
        database_response = (
            supabase.table("imports")
            .insert(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "checksum": checksum,
                    "file_size": len(content),
                    "idempotency_key": idempotency_key,
                    "storage_path": storage_path,
                    "status": "pending",
                }
            )
            .execute()
        )
    except APIError as exc:
        if exc.code == "23505":
            collision = _find_import(
                idempotency_key=idempotency_key, checksum=checksum
            )
            if collision:
                api_response.status_code = status.HTTP_200_OK
                return _check_idempotency_key(collision, checksum)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo completar el registro de la importación.",
        ) from exc

    if not database_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar la importación.",
        )
    return database_response.data[0]