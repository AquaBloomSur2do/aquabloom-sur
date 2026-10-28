from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

try:
    from postgrest.exceptions import APIError
except (ImportError, ModuleNotFoundError):
    try:
        from supabase.lib.client_options import APIError
    except (ImportError, ModuleNotFoundError):

        class APIError(Exception):
            code: str = "500"
            details: str = "Error genérico de BD"

            def __init__(self, error: object = None):
                super().__init__(error)
                if isinstance(error, dict):
                    self.code = str(error.get("code", self.code))
                    self.details = str(error.get("details", self.details))

from app.auth import verify_supabase_jwt
from app.database import supabase

from .schemas import PreparedInputCreate, PreparedInputResponse

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])


def _raise_database_error(exc: Exception) -> NoReturn:
    error_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if str(error_code) == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un insumo registrado para esta clave de origen.",
        ) from exc
    if str(error_code) == "23503":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe la importación del archivo original.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo registrar el insumo preparado.",
    ) from exc


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

    try:
        original = (
            supabase.table("imports")
            .select("id")
            .eq("id", str(prepared_input.original_import_id))
            .limit(1)
            .execute()
        )
    except APIError as exc:
        _raise_database_error(exc)
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    if not original or not getattr(original, "data", None):
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
        _raise_database_error(exc)
    except Exception as exc:  # noqa: BLE001
        _raise_database_error(exc)

    response_data = getattr(response, "data", None) if response else None
    if response_data and len(response_data) > 0:
        return response_data[0]
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="No se pudo registrar el insumo preparado.",
    )