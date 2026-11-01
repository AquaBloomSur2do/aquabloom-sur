import json
import logging

from app.config import Settings
from app.main import app
from app.queueing import TASK_QUEUE, get_redis_client
from app.worker import consume_once, execute_task
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

client = TestClient(app)


def test_health_endpoint_reports_service_status() -> None:
    app.dependency_overrides[get_redis_client] = lambda: FakeRedis()
    try:
        response = TestClient(app).get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "service": "AquaBloom Satellite",
        "environment": "development",
        "status": "ok",
        "queue": "connected",
    }


def test_settings_read_external_environment(monkeypatch) -> None:
    monkeypatch.setenv("SATELLITE_SERVICE_NAME", "Satellite Test")
    monkeypatch.setenv("SATELLITE_ENVIRONMENT", "test")

    settings = Settings(_env_file=None)

    assert settings.service_name == "Satellite Test"
    assert settings.environment == "test"


class FakeRedis:
    def __init__(self):
        self.messages = []

    def ping(self):
        return True

    def lpush(self, key, message):
        self.messages.insert(0, (key, message))

    def brpop(self, key, timeout=0):
        if not self.messages:
            return None
        queued_key, message = self.messages.pop()
        assert queued_key == key
        return queued_key, message


def test_health_checks_redis_connection():
    app.dependency_overrides[get_redis_client] = lambda: FakeRedis()
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["queue"] == "connected"


def test_health_reports_redis_unavailable():
    class UnavailableRedis:
        def ping(self):
            raise RedisError("redis is offline")

    app.dependency_overrides[get_redis_client] = lambda: UnavailableRedis()
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_enqueue_returns_task_id_and_pushes_message_to_redis():
    fake_redis = FakeRedis()
    app.dependency_overrides[get_redis_client] = lambda: fake_redis
    try:
        response = client.post(
            "/tasks/measurement-summary",
            json={"measurements": [1.0, 2.0, 6.0]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    queue_name, message = fake_redis.messages[0]
    task = json.loads(message)
    assert queue_name == TASK_QUEUE
    assert task["task_id"] == response.json()["task_id"]
    assert task["task_type"] == "summarize_measurements"
    assert task["measurements"] == [1.0, 2.0, 6.0]
    assert "results" not in task


def test_enqueued_task_is_consumed_and_executed_without_persisting_result(caplog):
    caplog.set_level(logging.INFO, logger="scientific-worker")
    fake_redis = FakeRedis()
    app.dependency_overrides[get_redis_client] = lambda: fake_redis
    try:
        response = client.post(
            "/tasks/measurement-summary",
            json={"measurements": [1.0, 3.0, 5.0]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert consume_once(fake_redis)
    assert "Tarea científica completada" in caplog.text
    assert response.json()["task_id"] in caplog.text
    assert not hasattr(fake_redis, "results")
    assert not consume_once(fake_redis)


def test_enqueue_fails_explicitly_when_redis_is_unavailable():
    class UnavailableRedis:
        def lpush(self, *_args):
            raise RedisError("redis is offline")

    app.dependency_overrides[get_redis_client] = lambda: UnavailableRedis()
    try:
        response = client.post(
            "/tasks/measurement-summary",
            json={"measurements": [1.0, 2.0]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_worker_executes_enqueued_task_from_separate_queue(caplog):
    caplog.set_level(logging.INFO, logger="scientific-worker")
    task = {
        "task_id": "task-456",
        "task_type": "summarize_measurements",
        "measurements": [1.0, 3.0, 5.0],
    }
    assert execute_task(json.dumps(task)) == {
        "task_id": "task-456",
        "count": 3,
        "minimum": 1.0,
        "maximum": 5.0,
        "mean": 3.0,
    }

    class Queue:
        def __init__(self):
            self.message = json.dumps(task)

        def brpop(self, _key, timeout=0):
            message, self.message = self.message, None
            return (TASK_QUEUE, message) if message is not None else None

    queue = Queue()
    assert consume_once(queue)
    assert "Tarea científica completada" in caplog.text
    assert not consume_once(queue)


def test_enqueue_rejects_empty_measurements():
    response = client.post(
        "/tasks/measurement-summary",
        json={"measurements": []},
    )

    assert response.status_code == 422


def test_enqueue_rejects_non_finite_measurements():
    response = client.post(
        "/tasks/measurement-summary",
        content='{"measurements":[1e10000]}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
