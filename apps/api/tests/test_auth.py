import os

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")

# Importamos la clase original de Supabase para interceptarla desde la raíz
from supabase.client import Client as SupabaseClient

from app import auth
from app import lakes as lakes_module
from app.main import app

# Datos falsos exactos para evitar que los validadores de la API colapsen
fake_data = [{
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Lago admin",
    "region": "Araucania",
    "description": "Creación autorizada",
    "geom": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]},
    "status": "active",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
}]

class FakeResponse:
    def __init__(self, data=None):
        self.data = fake_data if data is None else data
        self.count = len(self.data)

class MagicSupabaseMock:
    def __init__(self):
        self.inserted_data = None

    def __call__(self, *args, **kwargs): return self

    def insert(self, payload, *args, **kwargs):
        self.inserted_data = payload
        return self

    def execute(self, *args, **kwargs):
        response = FakeResponse()
        if self.inserted_data is not None:
            response.data = [
                {
                    **self.inserted_data,
                    "id": fake_data[0]["id"],
                    "status": "active",
                    "created_at": fake_data[0]["created_at"],
                    "updated_at": fake_data[0]["updated_at"],
                }
            ]
        return response

    def __getattr__(self, name):
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
    "name": "Lago Villarrica",
    "region": "Araucania",
    "description": "Creación autorizada",
    "geom": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]},
}

mock_admin_token = {
    "sub": "user-123",
    "id": "user-123",
    "user_metadata": {"role": "administrador"},
    "role": "administrador",
}


class FakeTable:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self._filters = {}
        self._payload = None
        self._count = False
        self._range = None

    def select(self, *args, **kwargs):
        self._count = kwargs.get("count") == "exact"
        return self

    def upsert(self, payload, **kwargs):
        self._payload = payload
        return self

    def eq(self, field, value):
        self._filters[field] = ("eq", value)
        return self

    def neq(self, field, value):
        self._filters[field] = ("neq", value)
        return self

    def ilike(self, field, value):
        self._filters[field] = ("ilike", value)
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def maybe_single(self):
        return self

    def execute(self):
        if self.table_name == "profiles":
            return type("Response", (), {"data": [{"id": "123e4567-e89b-12d3-a456-426614174000", "email": "user@test.com"}]})()
        if self.table_name == "memberships":
            return type(
                "Response",
                (),
                {
                    "data": [
                        {
                            "id": "11111111-1111-1111-1111-111111111111",
                            "user_id": "123e4567-e89b-12d3-a456-426614174000",
                            "role": "admin",
                            "status": "active",
                            "organization": {"id": "22222222-2222-2222-2222-222222222222", "name": "Org", "status": "active"},
                        }
                    ]
                },
            )()
        if self.table_name == "lakes":
            rows = list(self.db.tables.get("lakes", []))
            for field, (op, value) in self._filters.items():
                if op == "eq":
                    rows = [item for item in rows if str(item.get(field)) == str(value)]
                elif op == "neq":
                    rows = [item for item in rows if str(item.get(field)) != str(value)]
                elif op == "ilike":
                    pattern = value.replace("%", "").lower()
                    rows = [item for item in rows if pattern in str(item.get(field, "")).lower()]
            if self._range is not None:
                start, end = self._range
                rows = rows[start : end + 1]
            return type("Response", (), {"data": rows, "count": len(rows)})()
        return type("Response", (), {"data": []})()


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "lakes": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "name": "Lago Villarrica",
                    "region": "Araucania",
                    "description": "Creación autorizada",
                    "geom": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]},
                    "status": "active",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                }
            ],
            "profiles": [],
            "memberships": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "role": "admin",
                    "status": "active",
                    "organization": {"id": "22222222-2222-2222-2222-222222222222", "name": "Org", "status": "active"},
                }
            ],
        }

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_integracion_auth_me_y_lakes(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(auth, "supabase", fake_db)
    monkeypatch.setattr(lakes_module, "supabase", fake_db)

    user_uuid = "123e4567-e89b-12d3-a456-426614174000"
    payload = {
        "sub": user_uuid,
        "email": "user@test.com",
        "role": "administrador",
        "user_metadata": {"role": "administrador"},
    }

    app.dependency_overrides[auth.verify_supabase_jwt] = lambda: payload

    response_me = TestClient(app).get("/auth/me")
    assert response_me.status_code == 200
    assert response_me.json()["id"] == user_uuid
    assert response_me.json()["email"] == "user@test.com"

    response_lakes = TestClient(app).get("/api/v1/lakes")
    assert response_lakes.status_code == 200
    assert len(response_lakes.json()["items"]) >= 1

    app.dependency_overrides.clear()

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
    