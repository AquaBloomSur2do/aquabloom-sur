import json
from functools import lru_cache
from uuid import uuid4

from redis import Redis

from app.config import settings

TASK_QUEUE = "scientific:tasks"


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def enqueue_measurement_summary(
    measurements: list[float],
    redis_client: Redis,
) -> str:
    task_id = str(uuid4())
    redis_client.lpush(
        TASK_QUEUE,
        json.dumps(
            {
                "task_id": task_id,
                "task_type": "summarize_measurements",
                "measurements": measurements,
            },
            separators=(",", ":"),
        ),
    )
    return task_id
