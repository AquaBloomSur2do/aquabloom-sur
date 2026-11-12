from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.database import supabase
from apps.api.app.domains.ingestion.schemas_ingestion import (
    ImportResponse,
    PreparedInputCreate,
    PreparedInputResponse,
    SampleListResponse,
)
from apps.api.app.domains.ingestion.service_ingestion import (
    list_samples_service,
    process_file_import_service,
    register_prepared_input_service,
)

router = APIRouter()

imports_router = APIRouter(prefix="/api/v1/imports", tags=["Imports"])
ingestion_router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])
samples_router = APIRouter(prefix="/api/v1/samples", tags=["Samples"])


@imports_router.post(
    "", response_model=ImportResponse, status_code=status.HTTP_201_CREATED
)
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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="La clave de idempotencia no puede estar vacía.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de importación está vacío.",
        )

    record, is_existing = process_file_import_service(
        supabase,
        content=content,
        raw_filename=file.filename,
        content_type=file.content_type,
        idempotency_key=idempotency_key,
    )
    if is_existing:
        api_response.status_code = status.HTTP_200_OK
    return record


@ingestion_router.post(
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
    return register_prepared_input_service(supabase, prepared_input)


@samples_router.get("", response_model=SampleListResponse)
async def list_samples(
    quarantine: bool | None = Query(
        None, description="Filtrar por estado de cuarentena (true/false)"
    ),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Tamaño de página"),
):
    try:
        return list_samples_service(
            supabase, quarantine=quarantine, page=page, page_size=page_size
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al consultar las muestras: {e!s}",
        ) from e


router.include_router(imports_router)
router.include_router(ingestion_router)
router.include_router(samples_router)
