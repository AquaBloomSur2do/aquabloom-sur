import os
from types import SimpleNamespace

import jwt
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fakekey")

from app.config import settings
from app.main import app
from app.repositories import get_active_lakes


class FakeTable:
    def __init__(self, supabase):
        self.supabase = supabase
        self.filters = []
        self.payload = None

    @property
    def rows(self):
        return self.supabase.rows

    def _matches_filters(self, row):
        for op, column, value in self.filters:
            if op == "eq" and str(row.get(column)) != str(value):
                return False
            if op == "neq" and str(row.get(column)) == str(value):
                return False
            if op == "ilike":
                pattern = str(value).replace("%", "")
                if pattern.lower() not in str(row.get(column, "")).lower():
                    return False
            if op == "range":
                continue
        return True

    def select(self, *_args, **_kwargs):
        self.filters = []
        self.payload = None
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def neq(self, column, value):
        self.filters.append(("neq", column, value))
        return self

    def ilike(self, column, value):
        self.filters.append(("ilike", column, value))
        return self

    def range(self, start, end):
        self.filters.append(("range", start, end))
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def delete(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        matching_rows = [row for row in self.rows if self._matches_filters(row)]
        for op, column, value in self.filters:
            if op == "range":
                start, end = column, value
                matching_rows = matching_rows[start : end + 1]

        if self.payload is not None:
            updated_rows = []
            for index, row in enumerate(self.rows):
                if self._matches_filters(row):
                    updated_row = {**row, **self.payload}
                    self.supabase.rows[index] = updated_row
                    updated_rows.append(updated_row)
            self.payload = None
            self.filters = []
            return SimpleNamespace(data=updated_rows, count=len(updated_rows))

        self.filters = []
        return SimpleNamespace(data=matching_rows, count=len(matching_rows))


class FakeSupabase:
    def __init__(self, rows):
        self.rows = list(rows)

    def table(self, _name):
        return FakeTable(self)


def build_token(permissions=None, role="administrador", status="active"):
    payload = {
        "sub": "123e4567-e89b-12d3-a456-426614174000",
        "email": "user@example.com",
        "aud": "authenticated",
        "iss": f"{settings.supabase_url}/auth/v1",
        "user_metadata": {
            "role": role,
            "status": status,
            "permissions": permissions or [],
        },
        "app_metadata": {
            "role": role,
            "status": status,
            "permissions": permissions or [],
        },
    }
    if permissions is not None:
        payload["permissions"] = permissions
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def test_list_lakes_excludes_inactive(monkeypatch):
    settings.supabase_jwt_secret = "test-secret"
    settings.supabase_url = "https://example.supabase.co"
    lake_id = "123e4567-e89b-12d3-a456-426614174000"
    other_id = "223e4567-e89b-12d3-a456-426614174000"
    fake_client = FakeSupabase(
        [
            {
                "id": lake_id,
                "name": "Activo",
                "region": "Patagonia",
                "description": "Lago activo",
                "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": other_id,
                "name": "Inactivo",
                "region": "Andes",
                "description": "Lago inactivo",
                "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "status": "inactive",
                "created_at": "2024-01-02T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
            },
        ]
    )
    monkeypatch.setattr("app.database.supabase", fake_client)
    import app.lakes as lakes_module

    monkeypatch.setattr(lakes_module, "supabase", fake_client)

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


def test_get_lakes_list_excludes_inactive(client_with_authorized_lakes):
    response = client_with_authorized_lakes.get("/api/v1/lakes")

    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["status"] != "inactive" for item in items)
    assert not any(item["name"] == "Lago inactivo" for item in items)


def test_get_active_lakes_filters_and_transforms_entities():
    class FakeTable:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *args, **kwargs):
            return self

        def eq(self, field, value):
            return self

        def execute(self):
            return type("Response", (), {"data": list(self.rows)})()

    class FakeClient:
        def __init__(self, rows):
            self.rows = rows

        def table(self, table_name):
            assert table_name == "lakes"
            return FakeTable(self.rows)

    raw_rows = [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Lago activo",
            "region": "Lima",
            "description": "Activo",
            "status": "active",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "internal_note": "no debe exportarse",
        },
        {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Lago inactivo",
            "region": "Arequipa",
            "description": "Inactivo",
            "status": "inactive",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 0]]]},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "internal_note": "no debe exportarse",
        },
        {
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "Lago activo con flag",
            "region": "Cusco",
            "description": "Activo por bandera",
            "status": "inactive",
            "is_active": True,
            "geom": "POLYGON((0 0, 5 0, 5 5, 0 0))",
            "created_at": "2024-01-03T00:00:00Z",
            "updated_at": "2024-01-04T00:00:00Z",
            "internal_metadata": {"secret": "hidden"},
        },
    ]

    result = get_active_lakes(FakeClient(raw_rows))

    assert len(result) == 2
    assert all(item.status == "active" for item in result)
    assert {item.name for item in result} == {"Lago activo", "Lago activo con flag"}
    assert all("internal_note" not in item.model_dump() for item in result)
    assert all("internal_metadata" not in item.model_dump() for item in result)
    assert result[0].geom["type"] == "Polygon"
    assert result[1].geom["type"] == "Polygon"
    assert result[1].geom["coordinates"]


def test_get_lake_by_id_returns_active_lake(client_with_authorized_lakes):
    lake_id = "11111111-1111-1111-1111-111111111111"
    response = client_with_authorized_lakes.get(f"/api/v1/lakes/{lake_id}")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data["items"]] == [lake_id]


def test_delete_lake_requires_catalog_disable_permission(monkeypatch):
    settings.supabase_jwt_secret = "test-secret"
    settings.supabase_url = "https://example.supabase.co"
    lake_id = "123e4567-e89b-12d3-a456-426614174000"
    fake_client = FakeSupabase([
        {
            "id": lake_id,
            "name": "Activo",
            "region": "Patagonia",
            "description": "Lago activo",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ])
    monkeypatch.setattr("app.database.supabase", fake_client)
    import app.lakes as lakes_module

    monkeypatch.setattr(lakes_module, "supabase", fake_client)

    client = TestClient(app)
    response = client.delete(f"/api/v1/lakes/{lake_id}")
    assert response.status_code == 401

    token = build_token(permissions=["catalog:view"])
    response = client.delete(
        f"/api/v1/lakes/{lake_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_delete_lake_soft_deletes(monkeypatch):
    settings.supabase_jwt_secret = "test-secret"
    settings.supabase_url = "https://example.supabase.co"
    lake_id = "123e4567-e89b-12d3-a456-426614174000"
    fake_client = FakeSupabase([
        {
            "id": lake_id,
            "name": "Activo",
            "region": "Patagonia",
            "description": "Lago activo",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ])
    monkeypatch.setattr("app.database.supabase", fake_client)
    import app.lakes as lakes_module

    monkeypatch.setattr(lakes_module, "supabase", fake_client)

    client = TestClient(app)
    token = build_token(permissions=["catalog:disable"])
    response = client.delete(
        f"/api/v1/lakes/{lake_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "inactive"


def test_delete_lake_not_found_when_already_inactive(monkeypatch):
    settings.supabase_jwt_secret = "test-secret"
    settings.supabase_url = "https://example.supabase.co"
    lake_id = "123e4567-e89b-12d3-a456-426614174000"
    fake_client = FakeSupabase([
        {
            "id": lake_id,
            "name": "Inactivo",
            "region": "Patagonia",
            "description": "Lago ya desactivado",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            "status": "inactive",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        }
    ])
    monkeypatch.setattr("app.database.supabase", fake_client)
    import app.lakes as lakes_module

    monkeypatch.setattr(lakes_module, "supabase", fake_client)

    client = TestClient(app)
    token = build_token(permissions=["catalog:disable"])
    response = client.delete(
        f"/api/v1/lakes/{lake_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Lago no encontrado"


def test_delete_lake_soft_deletes_and_excludes_from_list(monkeypatch):
    settings.supabase_jwt_secret = "test-secret"
    settings.supabase_url = "https://example.supabase.co"
    lake_id = "123e4567-e89b-12d3-a456-426614174000"
    fake_client = FakeSupabase([
        {
            "id": lake_id,
            "name": "Activo",
            "region": "Patagonia",
            "description": "Lago activo",
            "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    ])
    monkeypatch.setattr("app.database.supabase", fake_client)
    import app.lakes as lakes_module

    monkeypatch.setattr(lakes_module, "supabase", fake_client)

    client = TestClient(app)
    token = build_token(permissions=["catalog:disable"])
    delete_response = client.delete(
        f"/api/v1/lakes/{lake_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert delete_response.status_code == 200

    list_response = client.get("/api/v1/lakes")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []


def test_lake_crud_rejects_unauthorized_users(client_with_unauthorized_lakes):
    payload = {
        "name": "Lago prohibido",
        "region": "Tacna",
        "description": "No debería crearse",
        "geom": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 5], [0, 0]]]},
    }

    create_response = client_with_unauthorized_lakes.post("/api/v1/lakes", json=payload)
    assert create_response.status_code == 403

    update_response = client_with_unauthorized_lakes.patch(
        "/api/v1/lakes/11111111-1111-1111-1111-111111111111",
        json={"name": "Intento cambiar"},
    )
    assert update_response.status_code == 403

    delete_response = client_with_unauthorized_lakes.delete(
        "/api/v1/lakes/11111111-1111-1111-1111-111111111111"
    )
    assert delete_response.status_code == 403


def test_get_lake_stations_returns_500_when_lake_query_fails(monkeypatch):
    def raise_database_unavailable(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        lakes_module,
        "get_lake_stations_from_db",
        raise_database_unavailable,
    )

    response = TestClient(app).get(
        "/api/v1/lakes/11111111-1111-1111-1111-111111111111/stations"
    )

    assert response.status_code == 500


def test_get_lake_stations_documents_station_response_model():
    operation = app.openapi()["paths"]["/api/v1/lakes/{lake_id}/stations"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert response_schema["type"] == "array"
    assert response_schema["items"]["$ref"] == "#/components/schemas/StationOut"
