import json
import logging
import math
import os
import signal
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

TASK_QUEUE = "scientific:tasks"
DEFAULT_REDIS_URL = "redis://redis:6379/0"
BRPOP_TIMEOUT_SECONDS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] scientific-worker: %(message)s",
)
logger = logging.getLogger("scientific-worker")

_shutdown_requested = False


@dataclass(frozen=True)
class MeasurementSummary:
    task_id: str
    count: int
    minimum: float
    maximum: float
    mean: float


def _handle_shutdown_signal(signum: int, _frame: Any) -> None:
    global _shutdown_requested
    logger.info(
        "Señal de apagado recibida (%s). Cerrando worker de forma segura.",
        signum,
    )
    _shutdown_requested = True


def summarize_measurements(
    task_id: str,
    measurements: Sequence[Any],
) -> MeasurementSummary:
    """Calcula estadísticas básicas validando que todos los valores sean numéricos y finitos."""
    if not measurements:
        raise ValueError("La lista de mediciones no puede estar vacía.")

    numeric_values: list[float] = []
    for raw_value in measurements:
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise TypeError("Todas las mediciones deben ser valores numéricos.")
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError("Todas las mediciones deben ser valores finitos.")
        numeric_values.append(value)

    count = len(numeric_values)
    return MeasurementSummary(
        task_id=task_id,
        count=count,
        minimum=min(numeric_values),
        maximum=max(numeric_values),
        mean=math.fsum(numeric_values) / count,
    )


def process_raw_task(raw_payload: str) -> MeasurementSummary:
    """Parsea y ejecuta un mensaje JSON proveniente de la cola Redis."""
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError("El mensaje de la cola no es un JSON válido.") from exc

    if not isinstance(payload, dict):
        raise TypeError("El payload de la tarea debe ser un objeto JSON.")

    task_id = str(payload.get("task_id", "")).strip()
    task_type = payload.get("task_type")
    measurements = payload.get("measurements")

    if not task_id:
        raise ValueError("El campo 'task_id' es obligatorio.")
    if task_type != "summarize_measurements":
        raise ValueError(f"Tipo de tarea no soportado: {task_type!r}.")
    if not isinstance(measurements, list):
        raise TypeError("El campo 'measurements' debe ser una lista.")

    return summarize_measurements(task_id=task_id, measurements=measurements)


def create_redis_client(redis_url: str | None = None) -> Redis:
    url = redis_url or os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    return Redis.from_url(url, decode_responses=True)


def run_worker_loop(redis_client: Redis) -> None:
    """Bucle principal del worker con consumo bloqueante y manejo seguro de errores."""
    redis_client.ping()
    logger.info(
        "Worker conectado a Redis y escuchando cola '%s' (version=%s).",
        TASK_QUEUE,
        os.getenv("APP_VERSION", "dev"),
    )

    while not _shutdown_requested:
        try:
            item = redis_client.brpop(TASK_QUEUE, timeout=BRPOP_TIMEOUT_SECONDS)
            if item is None:
                continue

            _queue_name, raw_payload = item
            summary = process_raw_task(raw_payload)
            logger.info(
                "Tarea completada | task_id=%s count=%d min=%.4f max=%.4f mean=%.4f",
                summary.task_id,
                summary.count,
                summary.minimum,
                summary.maximum,
                summary.mean,
            )
        except (ValueError, TypeError) as exc:
            logger.warning("Tarea descartada por formato inválido: %s", exc)
        except RedisError as exc:
            logger.error("Error de comunicación con Redis: %s", exc)


def main() -> int:
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    try:
        client = create_redis_client()
        run_worker_loop(client)
        return 0
    except RedisError as exc:
        logger.critical("No se pudo conectar a Redis al iniciar el worker: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())


