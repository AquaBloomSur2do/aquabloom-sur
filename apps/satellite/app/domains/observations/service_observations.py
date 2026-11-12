import json
import logging
import time
from typing import Any, Protocol
from uuid import UUID

from fastapi import HTTPException, status
from redis.exceptions import RedisError

from apps.satellite.app.core.queueing import TASK_QUEUE, get_redis_client
from apps.satellite.app.domains.observations.domain_observations import (
    summarize_measurements,
)
from apps.satellite.app.domains.observations.model_observations import (
    get_lake_organization_id,
    get_scene_lake_id,
    has_active_organization_membership,
    insert_spectral_observation_in_db,
    query_spectral_observations_with_fallback,
)
from apps.satellite.app.domains.observations.schemas_observations import (
    SpectralObservationCreate,
)

logger = logging.getLogger("scientific-worker")


def extract_observation_user_id(payload: dict) -> str:
    user_id = payload.get("sub")
    try:
        return str(UUID(str(user_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin ID de usuario.",
        ) from exc


def verify_scene_organization_access(client, scene_id: UUID, user_id: str) -> None:
    lake_id = get_scene_lake_id(client, scene_id)
    if not lake_id:
        raise HTTPException(status_code=404, detail="La escena no existe.")

    org_id = get_lake_organization_id(client, lake_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="El lago asociado no existe.")

    if not has_active_organization_membership(client, user_id, org_id):
        raise HTTPException(status_code=403, detail="No tienes permisos.")


def create_observation_service(
    client, payload: SpectralObservationCreate, user_id: str
) -> dict[str, Any]:
    verify_scene_organization_access(client, payload.scene_id, user_id)

    insert_data = {
        "scene_id": str(payload.scene_id),
        "sample_id": str(payload.sample_id),
        "bands": payload.bands,
        "spectral_index": payload.spectral_index,
        "index_value": payload.index_value,
        "unit": payload.unit,
        "quality": payload.quality.value,
    }

    try:
        created = insert_spectral_observation_in_db(client, insert_data)
        if not created:
            raise HTTPException(status_code=500, detail="No se devolvieron datos.")
        return created
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Error al guardar: {exc}"
        ) from exc


def get_observations_service(
    client, scene_id: UUID, sample_id: UUID, user_id: str
) -> list[dict[str, Any]]:
    verify_scene_organization_access(client, scene_id, user_id)
    return query_spectral_observations_with_fallback(client, scene_id, sample_id)


# --- Lógica del Worker de Redis (antes worker.py) ---


class QueueClient(Protocol):
    def brpop(self, key: str, timeout: int = 0) -> tuple[str, str] | None: ...


def execute_task(message: str) -> dict:
    task = json.loads(message)
    if task.get("task_type") != "summarize_measurements":
        raise ValueError("Tipo de tarea científica no reconocido.")

    result = summarize_measurements(task["measurements"])
    return {"task_id": task["task_id"], **result}


def consume_once(redis_client: QueueClient) -> bool:
    queued_task = redis_client.brpop(TASK_QUEUE, timeout=5)
    if queued_task is None:
        return False

    _, message = queued_task
    try:
        result = execute_task(message)
        logger.info("Tarea científica completada: %s", json.dumps(result))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.exception("No se pudo ejecutar una tarea científica.")
    return True


def run_worker() -> None:
    redis_client = get_redis_client()
    logger.info("Worker científico iniciado; esperando tareas en Redis.")

    while True:
        try:
            consume_once(redis_client)
        except RedisError:
            logger.exception(
                "No se pudo consumir tareas desde Redis; se reintentará."
            )
            time.sleep(2)

