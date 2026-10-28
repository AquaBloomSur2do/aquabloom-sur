from math import isfinite
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from redis import Redis
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings
from app.queueing import enqueue_measurement_summary, get_redis_client

app = FastAPI(
    title=settings.service_name,
    description="Servicio Satellite para encolar trabajos científicos.",
    version="v1",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Parámetros de entrada inválidos."},
    )


class MeasurementSummaryRequest(BaseModel):
    measurements: list[Annotated[float, Field(allow_inf_nan=False)]] = Field(
        min_length=1,
        max_length=10000,
    )


class EnqueuedTaskResponse(BaseModel):
    task_id: str
    status: str


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "environment": settings.environment,
    }


@app.get("/health", tags=["System"])
def health_check(
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> dict[str, str]:
    try:
        redis_client.ping()
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis no está disponible.",
        ) from exc

    return {
        "service": settings.service_name,
        "environment": settings.environment,
        "status": "ok",
        "queue": "connected",
    }


@app.post(
    "/tasks/measurement-summary",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EnqueuedTaskResponse,
)
def enqueue_summary(
    request: MeasurementSummaryRequest,
    redis_client: Annotated[Redis, Depends(get_redis_client)],
) -> EnqueuedTaskResponse:
    if not all(isfinite(value) for value in request.measurements):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Todas las mediciones deben ser valores finitos.",
        )

    try:
        task_id = enqueue_measurement_summary(request.measurements, redis_client)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo encolar la tarea científica en Redis.",
        ) from exc

    return EnqueuedTaskResponse(task_id=task_id, status="queued")
