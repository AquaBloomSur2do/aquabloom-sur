import json
from functools import lru_cache
from uuid import uuid4

from redis import Redis

try:
    from apps.satellite.app.core.config import settings
except ModuleNotFoundError:
    from apps.satellite.app.core.config import settings

TASK_QUEUE = "scientific:tasks"


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def enqueue_measurement_summary(
    measurements: list[float],
    redis_client: Redis,
    correlation_id: str | None = None,
) -> str:
    task_id = str(uuid4())
    task = {
        "task_id": task_id,
        "task_type": "summarize_measurements",
        "measurements": measurements,
    }
    if correlation_id:
        task["correlation_id"] = correlation_id

    redis_client.lpush(
        TASK_QUEUE,
        json.dumps(task, separators=(",", ":")),
    )
    return task_id
