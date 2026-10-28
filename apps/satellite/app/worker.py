import json
import logging
import time
from typing import Protocol

from redis.exceptions import RedisError

from app.queueing import TASK_QUEUE, get_redis_client
from app.tasks import summarize_measurements

logger = logging.getLogger("scientific-worker")


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
            logger.exception("No se pudo consumir tareas desde Redis; se reintentará.")
            time.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
