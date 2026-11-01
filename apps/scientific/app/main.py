from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings

tags_metadata = [
    {"name": "System", "description": "Endpoints del sistema."},
    {"name": "Scientific", "description": "Entrenamiento de modelos y estimaciones."},
]

app = FastAPI(
    title="AquaBloom Sur Scientific API",
    description="Microservicio científico para el piloto de estimaciones de Clorofila-a.",
    version="v1",
    servers=[{"url": "http://localhost:8002"}],
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
            "details": exc.errors(),
        },
    )


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
    return {"message": f"Servicio Scientific inicializado en ambiente: {settings.environment}"}


@app.get("/api/v1/health", tags=["System"])
def health_check():
    return {
        "service": "AquaBloom Sur Scientific API",
        "version": "v1",
        "status": "ok",
    }
