
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient
from pydantic import SecretStr

# 1. Envolvemos el token en SecretStr para que coincida con el modelo de configuración
settings.internal_service_token = SecretStr("test-secret-token")

client = TestClient(app)

# 2. Definimos los headers de autorización para usar en las pruebas
HEADERS = {"X-Internal-Token": "test-secret-token"}


def test_create_execution_job_returns_202():
    payload = {
        "job_type": "estimation",
        "config": {
            "model_id": "model_v1",
            "scene_id": "scene_001",
        },
    }
    
    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert "status_url" in data
    assert data["job_id"] in data["status_url"]


def test_get_job_status_returns_200():
    payload = {
        "job_type": "training",
        "config": {
            "dataset_id": "dataset_123",
            "epochs": 50,
            "learning_rate": 0.01,
        },
    }
    post_response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert post_response.status_code == 202
    
    job_id = post_response.json()["job_id"]
    
    response = client.get(f"/api/v1/executions/{job_id}", headers=HEADERS)
    
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert "status" in data


def test_get_job_status_returns_404_for_invalid_id():
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/executions/{fake_uuid}", headers=HEADERS)
    
    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."


def test_create_execution_job_invalid_payload():
    invalid_payload = {
        "job_type": "training",
        "config": {
            "invalid_field": 123
        }
    }
    response = client.post("/api/v1/executions/", json=invalid_payload, headers=HEADERS)
    assert response.status_code == 422


def test_create_execution_job_rejects_without_token():
    payload = {
        "job_type": "estimation",
        "config": {
            "model_id": "model_v1",
            "scene_id": "scene_001",
        },
    }
    # Petición SIN los headers, debe ser rechazada con 401
    response = client.post("/api/v1/executions/", json=payload)
    
    assert response.status_code == 401
    assert response.json()["message"] == "Autenticación interna requerida."

