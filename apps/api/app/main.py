from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.app.core.auth import AuthException
from apps.api.app.core.auth import router as auth_router
from apps.api.app.core.config import settings
from apps.api.app.core.database import check_supabase_connection
from apps.api.app.core.dependencies import require_permission
from apps.api.app.core.handlers import (
    auth_exception_handler,
    global_exception_handler,
)
from apps.api.app.domains.catalog.controller_catalog import (
    router as catalog_router,
)
from apps.api.app.domains.dataset.controller_dataset import (
    router as dataset_router,
)
from apps.api.app.domains.identity.controller_identity import (
    router as identity_router,
)
from apps.api.app.domains.ingestion.controller_ingestion import (
    router as ingestion_router,
)
from apps.api.app.gateway.controller_gateway import router as gateway_router

from apps.satellite.app.domains.observations.controller_observations import (
    router as observations_router,
)
from apps.satellite.app.domains.scenes.controller_scenes import (
    router as scenes_router,
)
from apps.scientific.app.domains.execution.controller_execution import (
    router as execution_router,
)

tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Auth", "description": "Autenticación de usuarios."},
    {"name": "Organizations", "description": "Gestión de organizaciones de usuarios."},
    {"name": "Catalog", "description": "Catálogo de lagos y estaciones."},
    {"name": "Dashboard", "description": "Resumen de métricas del dashboard."},
    {"name": "Imports", "description": "Importación idempotente de archivos."},
    {"name": "Ingestion", "description": "Registro de insumos preparados."},
    {"name": "Samples", "description": "Consulta de muestras limnológicas."},
    {"name": "Observations", "description": "Observaciones espectrales."},
    {"name": "Datasets", "description": "Versionado y manifiestos de datasets."},
    {"name": "Manifests", "description": "Trazabilidad y validación criptográfica."},
]

app = FastAPI(
    title="AquaBloom Sur API",
    description="API REST para el manejo de usuarios, control de roles y catálogo de lagos.",
    version="v1",
    servers=[{"url": "http://localhost:8000"}],
    openapi_tags=tags_metadata,
)

COMMON_RESPONSES = {
    404: {
        "description": "Not Found",
        "content": {
            "application/json": {
                "example": {
                    "error": "Not Found",
                    "message": "Recurso no encontrado",
                }
            }
        },
    },
    422: {
        "description": "Validation Error",
        "content": {
            "application/json": {
                "example": {
                    "error": "Validation Error",
                    "message": "Parámetros inválidos",
                    "details": [],
                }
            }
        },
    },
    500: {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "example": {
                    "error": "Internal Error",
                    "message": "Error inesperado",
                }
            }
        },
    },
}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Not Found" if exc.status_code == 404 else "HTTP Error",
            "message": str(exc.detail),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Parámetros de entrada inválidos",
            "details": exc.errors(),
        },
    )


app.add_exception_handler(AuthException, auth_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(auth_router)
app.include_router(gateway_router)
app.include_router(identity_router)
app.include_router(catalog_router)
app.include_router(ingestion_router)
app.include_router(dataset_router, responses=COMMON_RESPONSES)
app.include_router(scenes_router)
app.include_router(observations_router, responses=COMMON_RESPONSES)
app.include_router(execution_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Idempotency-Key",
        "X-Correlation-ID",
    ],
)


@app.get("/")
def read_root():
    return {"message": f"API inicializada en ambiente: {settings.environment}"}


@app.get("/api/v1/health", tags=["System"])
def health_check():
    db_status = check_supabase_connection()
    return {
        "service": "AquaBloom Sur",
        "version": "v1",
        "status": "ok" if db_status["status"] == "ok" else "degraded",
        "database": db_status,
    }


@app.get(
    "/api/test-permission",
    dependencies=[Depends(require_permission("admin"))],
    tags=["System"],
)
def test_permission_route() -> dict:
    return {"message": "Acceso permitido. Tienes el rol correcto."}
