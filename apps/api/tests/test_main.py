import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app.core.config import Settings
from apps.api.app.main import app

client = TestClient(app)


def test_health_check():
    """Prueba GET /health comprobando código 200 y cuerpo básico."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert len(data) > 0


def test_404_format():
    """Prueba el formato unificado para rutas inexistentes."""
    response = client.get("/api/v1/ruta-falsa-que-no-existe")
    assert response.status_code == 404
    data = response.json()

    # Verifica que coincida con el esquema ErrorResponse definido previamente
    assert "error" in data
    assert "message" in data


def test_validation_error_format():
    """Prueba el formato unificado para errores 422 inyectando un tipo inválido."""
    # Forzamos 422 usando la ruta del catálogo que existe y exige enteros
    response = client.get("/api/v1/lakes?page=letras")
    assert response.status_code == 422
    data = response.json()

    assert "error" in data
    assert "message" in data
    assert "details" in data


def test_cors_allows_and_exposes_correlation_headers():
    preflight = client.options(
        "/api/v1/scientific/jobs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization,content-type,x-organization-id,"
                "x-idempotency-key,x-correlation-id,x-request-id"
            ),
        },
    )

    assert preflight.status_code == 200
    allowed_headers = preflight.headers.get("access-control-allow-headers", "").lower()
    assert "x-organization-id" in allowed_headers
    assert "x-idempotency-key" in allowed_headers
    assert "x-correlation-id" in allowed_headers
    assert "x-request-id" in allowed_headers
    response = client.get(
        "/",
        headers={"Origin": "http://localhost:5173"},
    )
    assert (
        response.headers.get("access-control-expose-headers", "").lower()
        == "x-correlation-id"
    )


def test_missing_configuration(monkeypatch):
    """Verifica que el sistema falle rápido si faltan variables de entorno."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)

    with pytest.raises(ValidationError):
        # _env_file=None evita que Pydantic lea secretamente el archivo local
        Settings(_env_file=None)
