"""Pruebas locales S3-015 (AQU-369): enrutamiento público del Gateway.

Cubre dos criterios de aceptación:

* Los prefijos públicos ``/api/v1/satellite`` y ``/api/v1/scientific`` llegan
  al servicio configurado correcto, conservando método, ruta, query, cuerpo y
  cabeceras.
* Cuando la dependencia está caída o no disponible (error de transporte o
  tiempo de espera), el Gateway responde HTTP 503 Service Unavailable con el
  sobre estándar de error ``{error, message, details}`` y el
  ``X-Correlation-ID`` correspondiente.
"""

from typing import Self

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api.app.gateway import controller_gateway, service_gateway
from apps.api.app.main import app

client = TestClient(app)

SERVICE_CASES = [
    ("satellite", "satellite_service_url"),
    ("scientific", "scientific_service_url"),
]

DEPENDENCY_ERROR_BODY = {
    "error": "ServiceUnavailable",
    "message": "La dependencia solicitada no está disponible.",
    "details": None,
}


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.response = httpx.Response(200, content=b"ok")


class _FakeAsyncClient:
    def __init__(self, recorder: _Recorder) -> None:
        self._recorder = recorder

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def request(self, method, url, headers, content):
        self._recorder.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "content": content,
            }
        )
        if self._recorder.error is not None:
            raise self._recorder.error
        return self._recorder.response


@pytest.fixture
def service_urls(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    urls = {
        "satellite_service_url": "https://satellite.example.test",
        "scientific_service_url": "https://scientific.example.test",
    }
    for attribute, value in urls.items():
        monkeypatch.setattr(controller_gateway.settings, attribute, value)
    return urls


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    fake = _Recorder()
    monkeypatch.setattr(
        service_gateway.httpx,
        "AsyncClient",
        lambda: _FakeAsyncClient(fake),
    )
    return fake


@pytest.mark.parametrize(("prefix", "url_setting"), SERVICE_CASES)
@pytest.mark.parametrize(
    ("suffix", "expected_path"),
    [
        ("", "/"),
        ("/scenes", "/scenes"),
        ("/scenes/abc?limit=5&page=2", "/scenes/abc?limit=5&page=2"),
    ],
    ids=["root", "single-segment", "nested-with-query"],
)
def test_prefix_is_forwarded_to_its_configured_service(
    recorder: _Recorder,
    service_urls: dict[str, str],
    prefix: str,
    url_setting: str,
    suffix: str,
    expected_path: str,
):
    response = client.get(f"/api/v1/{prefix}{suffix}")

    assert response.status_code == 200
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == f"{service_urls[url_setting]}{expected_path}"

    other_setting = (
        "scientific_service_url"
        if url_setting == "satellite_service_url"
        else "satellite_service_url"
    )
    assert not call["url"].startswith(service_urls[other_setting])


@pytest.mark.parametrize(("prefix", "url_setting"), SERVICE_CASES)
def test_prefix_forwards_method_body_and_headers(
    recorder: _Recorder,
    service_urls: dict[str, str],
    prefix: str,
    url_setting: str,
):
    response = client.post(
        f"/api/v1/{prefix}/jobs?mode=async",
        headers={
            "Authorization": "Bearer user-jwt",
            "X-Correlation-ID": "trace-123",
        },
        json={"lake_id": "lake-1"},
    )

    assert response.status_code == 200
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == f"{service_urls[url_setting]}/jobs?mode=async"
    assert call["content"] == b'{"lake_id":"lake-1"}'
    assert call["headers"]["authorization"] == "Bearer user-jwt"
    assert call["headers"]["X-Correlation-ID"] == "trace-123"
    assert response.headers["x-correlation-id"] == "trace-123"


@pytest.mark.parametrize(("prefix", "url_setting"), SERVICE_CASES)
@pytest.mark.parametrize("method", service_gateway.PROXY_METHODS)
def test_all_proxy_methods_reach_the_prefix(
    recorder: _Recorder,
    service_urls: dict[str, str],
    prefix: str,
    url_setting: str,
    method: str,
):
    response = client.request(method, f"/api/v1/{prefix}/status")

    assert response.status_code == 200
    assert len(recorder.calls) == 1
    assert recorder.calls[0]["method"] == method
    assert recorder.calls[0]["url"] == f"{service_urls[url_setting]}/status"


@pytest.mark.parametrize(("prefix", "url_setting"), SERVICE_CASES)
def test_upstream_response_is_forwarded_unchanged(
    recorder: _Recorder,
    service_urls: dict[str, str],
    prefix: str,
    url_setting: str,
):
    recorder.response = httpx.Response(
        202,
        content=b"accepted",
        headers={"X-Upstream": "yes"},
    )

    response = client.get(f"/api/v1/{prefix}/jobs")

    assert response.status_code == 202
    assert response.content == b"accepted"
    assert response.headers["x-upstream"] == "yes"


@pytest.mark.parametrize(("prefix", "url_setting"), SERVICE_CASES)
@pytest.mark.parametrize(
    "transport_error",
    [
        httpx.ConnectError("connection refused"),
        httpx.ConnectTimeout("timed out"),
        httpx.ReadError("connection reset"),
    ],
    ids=["connect-error", "connect-timeout", "read-error"],
)
def test_down_dependency_returns_documented_error(
    recorder: _Recorder,
    service_urls: dict[str, str],
    prefix: str,
    url_setting: str,
    transport_error: Exception,
):
    recorder.error = transport_error

    response = client.get(
        f"/api/v1/{prefix}/status",
        headers={"X-Correlation-ID": "trace-down"},
    )

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["x-correlation-id"] == "trace-down"
    assert response.json() == DEPENDENCY_ERROR_BODY

    body_text = response.text.lower()
    assert "connection refused" not in body_text
    assert "timed out" not in body_text
    assert "connection reset" not in body_text


def test_down_dependency_generates_correlation_id_when_missing(
    recorder: _Recorder,
    service_urls: dict[str, str],
):
    recorder.error = httpx.ConnectError("connection refused")

    response = client.get("/api/v1/scientific/status")

    assert response.status_code == 503
    assert response.json() == DEPENDENCY_ERROR_BODY
    correlation_id = response.headers["x-correlation-id"]
    assert correlation_id
    assert correlation_id != ""
