from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_health_endpoint_reports_service_status() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "AquaBloom Satellite",
        "environment": "development",
        "status": "ok",
    }


def test_settings_read_external_environment(monkeypatch) -> None:
    monkeypatch.setenv("SATELLITE_SERVICE_NAME", "Satellite Test")
    monkeypatch.setenv("SATELLITE_ENVIRONMENT", "test")

    settings = Settings(_env_file=None)

    assert settings.service_name == "Satellite Test"
    assert settings.environment == "test"
