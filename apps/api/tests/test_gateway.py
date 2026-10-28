import httpx
import pytest
from app import gateway
from app.main import app
from fastapi.testclient import TestClient

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

    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        gateway.settings,
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

    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/api/v1/satellite/status")

    assert captured_headers["X-Correlation-ID"]
    assert response.headers["x-correlation-id"] == captured_headers[
        "X-Correlation-ID"
    ]