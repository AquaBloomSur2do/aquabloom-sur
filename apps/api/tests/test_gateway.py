import json
import logging
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.app.gateway import controller_gateway, service_gateway
from apps.api.app.main import app
from apps.satellite.app.core.queueing import get_redis_client
from apps.satellite.app.main import app as satellite_app
from apps.scientific.app.main import app as scientific_app
from apps.scientific.app.worker import process_raw_task

client = TestClient(app)


@pytest.mark.parametrize(
    ("service", "url_setting"),
    [
        ("satellite", "satellite_service_url"),
        ("scientific", "scientific_service_url"),
    ],
)
def test_gateway_forwards_identity_and_correlation_id(
    monkeypatch: pytest.MonkeyPatch,
    service: str,
    url_setting: str,
):
    captured_request = {}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def request(self, method, url, headers, content):
            captured_request.update(
                method=method,
                url=url,
                headers=headers,
                content=content,
            )
            return httpx.Response(202, content=b"accepted")

    monkeypatch.setattr(service_gateway.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        controller_gateway.settings,
        url_setting,
        f"https://{service}.example.test/base",
    )

    response = client.post(
        f"/api/v1/{service}/jobs?mode=async",
        headers={
            "Authorization": "Bearer user-jwt",
            "X-Correlation-ID": "trace-123",
        },
        json={"lake_id": "lake-1"},
    )

    assert response.status_code == 202
    assert response.content == b"accepted"
    assert captured_request["method"] == "POST"
    assert captured_request["url"] == (
        f"https://{service}.example.test/base/jobs?mode=async"
    )
    assert captured_request["headers"]["authorization"] == "Bearer user-jwt"
    assert captured_request["headers"]["X-Correlation-ID"] == "trace-123"
    assert response.headers["x-correlation-id"] == "trace-123"
    assert b'{"lake_id":"lake-1"}' == captured_request["content"]


def test_gateway_generates_correlation_id_when_missing(monkeypatch: pytest.MonkeyPatch):
    captured_headers = {}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return None

        async def request(self, method, url, headers, content):
            captured_headers.update(headers)
            return httpx.Response(200)

    monkeypatch.setattr(service_gateway.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/api/v1/satellite/status")

    assert captured_headers["X-Correlation-ID"]
    assert response.headers["x-correlation-id"] == captured_headers["X-Correlation-ID"]


@pytest.mark.parametrize("incoming_correlation_id", ["trace-scientific-789", None])
def test_gateway_propagates_correlation_id_to_scientific(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    incoming_correlation_id: str | None,
):
    caplog.set_level(logging.INFO)
    async_client_type = httpx.AsyncClient
    monkeypatch.setattr(
        service_gateway.httpx,
        "AsyncClient",
        lambda: async_client_type(
            transport=httpx.ASGITransport(app=scientific_app),
            base_url="http://scientific",
        ),
    )
    monkeypatch.setattr(
        controller_gateway.settings,
        "scientific_service_url",
        "http://scientific",
    )

    headers = {}
    if incoming_correlation_id:
        headers["X-Correlation-ID"] = incoming_correlation_id
    response = client.get(
        "/api/v1/scientific/api/v1/health",
        headers=headers,
    )

    assert response.status_code == 200
    correlation_id = response.headers["x-correlation-id"]
    if incoming_correlation_id:
        assert correlation_id == incoming_correlation_id
    else:
        uuid.UUID(correlation_id)
    assert any(
        record.name == "apps.scientific.app.main"
        and getattr(record, "correlation_id", None) == correlation_id
        for record in caplog.records
    )


@pytest.mark.parametrize("incoming_correlation_id", ["trace-client-456", None])
def test_gateway_correlation_reaches_satellite_queue_and_worker(
    monkeypatch: pytest.MonkeyPatch,
    incoming_correlation_id: str | None,
):
    class FakeRedis:
        def __init__(self):
            self.messages = []

        def lpush(self, queue_name, message):
            self.messages.append((queue_name, message))

    redis_client = FakeRedis()
    monkeypatch.setitem(
        satellite_app.dependency_overrides,
        get_redis_client,
        lambda: redis_client,
    )
    monkeypatch.setattr(
        controller_gateway.settings,
        "satellite_service_url",
        "http://satellite",
    )
    async_client_type = httpx.AsyncClient
    monkeypatch.setattr(
        service_gateway.httpx,
        "AsyncClient",
        lambda: async_client_type(
            transport=httpx.ASGITransport(app=satellite_app),
            base_url="http://satellite",
        ),
    )

    headers = {}
    if incoming_correlation_id:
        headers["X-Correlation-ID"] = incoming_correlation_id
    response = client.post(
        "/api/v1/satellite/tasks/measurement-summary",
        headers=headers,
        json={"measurements": [1.0, 2.0, 3.0]},
    )

    assert response.status_code == 202
    correlation_id = response.headers["x-correlation-id"]
    if incoming_correlation_id:
        assert correlation_id == incoming_correlation_id
    else:
        uuid.UUID(correlation_id)

    assert len(redis_client.messages) == 1
    _, raw_task = redis_client.messages[0]
    task = json.loads(raw_task)
    assert task["correlation_id"] == correlation_id

    worker_result = process_raw_task(raw_task)
    assert worker_result.correlation_id == correlation_id
    assert worker_result.count == 3
