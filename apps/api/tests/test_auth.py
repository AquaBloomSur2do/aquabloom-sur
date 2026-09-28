import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

import app.lakes as lakes_module
from app import auth
from app.main import app


class FakeLakeTable:
    def __init__(self, payload):
        self.payload = payload

    def insert(self, data):
        self.payload["data"] = [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": data["name"],
                "region": data["region"],
                "description": data.get("description"),
                "geom": data["geom"],
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]
        return self

    def execute(self):
        return type("Response", (), {"data": self.payload["data"]})()


class FakeSupabaseLakeDB:
    def table(self, table_name):
        assert table_name == "lakes"
        return FakeLakeTable({})


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_token_valido(client):
    app.dependency_overrides[auth.verify_supabase_jwt] = lambda: {"user_metadata": {"role": "administrador"}}

    response = client.get(
        "/api/test-permission",
        headers={"Authorization": "Bearer token-admin"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Acceso permitido. Tienes el rol correcto."


def test_token_ausente(client):
    response = client.get("/api/test-permission")
    assert response.status_code == 401
    assert "message" in response.json()
    assert response.json()["message"] == "Usuario no autenticado"


def test_token_vencido(client):
    def mock_expired():
        raise HTTPException(status_code=401, detail="Token expired")

    app.dependency_overrides[auth.verify_supabase_jwt] = mock_expired

    response = client.post(
        "/api/v1/lakes",
        json={
            "name": "Lago prueba",
            "region": "Lima",
            "description": "Debe fallar por token vencido",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        },
    )
    assert response.status_code == 401
    assert response.json()["message"] == "Token expired"


def test_permiso_correcto(client, monkeypatch):
    monkeypatch.setattr(lakes_module, "supabase", FakeSupabaseLakeDB())
    app.dependency_overrides[auth.verify_supabase_jwt] = lambda: {"user_metadata": {"role": "administrador"}}

    response = client.post(
        "/api/v1/lakes",
        json={
            "name": "Lago admin",
            "region": "Arequipa",
            "description": "Creación autorizada",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]},
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Lago admin"


def test_permiso_insuficiente(client):
    app.dependency_overrides[auth.verify_supabase_jwt] = lambda: {"user_metadata": {"role": "usuario"}}

    response = client.post(
        "/api/v1/lakes",
        json={
            "name": "Lago restringido",
            "region": "Cusco",
            "description": "No debería crear",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 0]]]},
        },
    )
    assert response.status_code == 403
    assert "message" in response.json()
    assert response.json()["message"] == "No tienes permisos para crear lagos."
    