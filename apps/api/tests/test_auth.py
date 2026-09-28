import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

# Importamos la clase original de Supabase para interceptarla desde la raíz
from supabase.client import Client as SupabaseClient

from app import auth
from app.main import app

# Datos falsos exactos para evitar que los validadores de la API colapsen
fake_data = [{
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Lago admin",
    "region": "Arequipa",
    "description": "Creación autorizada",
    "geom": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]},
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
}]

class FakeResponse:
    def __init__(self):
        self.data = fake_data
        self.count = len(fake_data)

class MagicSupabaseMock:
    def __call__(self, *args, **kwargs): return self
    def __getattr__(self, name):
        if name == "execute":
            return lambda *args, **kwargs: FakeResponse()
        return lambda *args, **kwargs: self

@pytest.fixture
def client(monkeypatch):
    # PARCHE MAESTRO: Intercepta cualquier uso de Supabase en todo el proyecto
    # garantizando que ninguna prueba intente conectarse a internet.
    monkeypatch.setattr(SupabaseClient, "table", lambda self, name: MagicSupabaseMock())
    
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

dummy_payload = {
    "name": "Lago admin",
    "region": "Arequipa",
    "description": "Creación autorizada",
    "geom": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]}
}

mock_admin_token = {
    "sub": "user-123",
    "id": "user-123",
    "user_metadata": {"role": "administrador"},
    "role": "administrador"
}

def test_token_valido(client):
    app.dependency_overrides[auth.verify_supabase_jwt] = lambda: mock_admin_token
    # Usamos POST en todas las pruebas para forzar que pasen por el validador de tokens
    response = client.post("/api/v1/lakes", headers={"Authorization": "Bearer token-admin"}, json=dummy_payload)
    assert response.status_code in [200, 201]

def test_token_ausente(client):
    response = client.post("/api/v1/lakes", json=dummy_payload)
    assert response.status_code == 401
    assert "message" in response.json()
    assert response.json()["message"] == "Not authenticated"

def test_token_vencido(client):
    def mock_expired():
        raise HTTPException(status_code=401, detail="Token expired")
    app.dependency_overrides[auth.verify_supabase_jwt] = mock_expired
    
    response = client.post("/api/v1/lakes", json=dummy_payload)
    assert response.status_code == 401
    assert response.json()["message"] == "Token expired"

def test_permiso_correcto(client):
    app.dependency_overrides[auth.verify_supabase_jwt] = lambda: mock_admin_token
    response = client.post("/api/v1/lakes", json=dummy_payload)
    assert response.status_code == 201
    assert response.json()["name"] == dummy_payload["name"]

def test_permiso_insuficiente(client):
    app.dependency_overrides[auth.verify_supabase_jwt] = lambda: {"sub": "user-456", "user_metadata": {"role": "usuario"}}
    response = client.post("/api/v1/lakes", json=dummy_payload)
    assert response.status_code == 403
    assert "message" in response.json()
    assert response.json()["message"] == "No tienes permisos para crear lagos."
    