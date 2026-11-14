from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.scientific.app.core.config import settings
from apps.scientific.app.domains.execution.controller_execution import (
    router as execution_router,
)
from apps.scientific.app.domains.model_scope.controller_model_scope import (
    router as model_scope_router,
)

tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Scientific", "description": "Entrenamiento de modelos y estimaciones."},
    {"name": "Executions", "description": "Ejecución y estado de trabajos científicos."},
]

app = FastAPI(
    title="AquaBloom Sur Scientific API",
    description="Microservicio científico para el piloto de estimaciones de Clorofila-a.",
    version="v1",
    servers=[{"url": "http://localhost:8003"}],
    openapi_tags=tags_metadata,
)


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
            "details": jsonable_encoder(exc.errors()),
        },
    )


app.include_router(execution_router)
app.include_router(model_scope_router)

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
    ],
)


@app.get("/")
def read_root():
    return {
        "message": f"Servicio Scientific inicializado en ambiente: {settings.environment}"
    }


@app.get("/api/v1/health", tags=["System"])
def health_check():
    return {
        "service": "AquaBloom Sur Scientific API",
        "version": "v1",
        "status": "ok",
    }
