from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from postgrest.exceptions import APIError

from app.auth import verify_supabase_jwt
from app.database import supabase

from .schemas import PreparedInputCreate, PreparedInputResponse

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])


@router.post(
    "/prepared",
    response_model=PreparedInputResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prepared_input(
    prepared_input: PreparedInputCreate,
    _user: Annotated[dict, Depends(verify_supabase_jwt)],
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible.",
        )

    original = (
        supabase.table("imports")
        .select("id")
        .eq("id", str(prepared_input.original_import_id))
        .limit(1)
        .execute()
    )
    if not original.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la importación del archivo original.",
        )

    try:
        response = (
            supabase.table("prepared_inputs")
            .insert(
                {
                    "original_import_id": str(prepared_input.original_import_id),
                    "source_key": prepared_input.source_key,
                    "metadata": prepared_input.metadata,
                }
            )
            .execute()
        )
    except APIError as exc:
        if exc.code == "23505":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un insumo registrado para esta clave de origen.",
            ) from exc
        if exc.code == "23503":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No existe la importación del archivo original.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo registrar el insumo preparado.",
        ) from exc

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo registrar el insumo preparado.",
        )
    return response.data[0]