from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title=settings.service_name,
    description="Servicio ASGI para los procesos de Satellite de AquaBloom Sur.",
    version="v1",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "environment": settings.environment,
    }


@app.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "environment": settings.environment,
        "status": "ok",
    }
