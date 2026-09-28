import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from app import auth
from app import lakes as lakes_module
from app import repositories as repositories_module
from app.main import app
from app.repositories import get_active_lakes


class FakeResponse:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count if count is not None else len(data)


class FakeTable:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self._filters = {}
        self._select = False
        self._insert_payload = None
        self._update_payload = None
        self._range = None

    def select(self, *args, **kwargs):
        self._select = True
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

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def update(self, payload):
        self._update_payload = payload
        return self

    def range(self, start, end):
        self._range = (start, end)
        return self

    def execute(self):
        items = list(self.db.lakes)

        for field, (op, value) in self._filters.items():
            if op == "eq":
                items = [item for item in items if str(item.get(field)) == str(value)]
            elif op == "neq":
                items = [item for item in items if str(item.get(field)) != str(value)]
            elif op == "ilike":
                pattern = value.replace("%", "")
                items = [
                    item for item in items if pattern.lower() in str(item.get(field, "")).lower()
                ]

        if self._insert_payload is not None:
            payload = {**self._insert_payload}
            payload.setdefault("id", str(uuid.uuid4()))
            payload.setdefault("status", "active")
            payload.setdefault("created_at", "2024-01-01T00:00:00Z")
            payload.setdefault("updated_at", "2024-01-01T00:00:00Z")
            self.db.lakes.append(payload)
            return FakeResponse([payload], count=len(self.db.lakes))

        if self._update_payload is not None:
            for item in items:
                for key, value in self._update_payload.items():
                    item[key] = value
                item["updated_at"] = "2024-01-02T00:00:00Z"
            return FakeResponse(items, count=len(items))

        if self._range is not None:
            start, end = self._range
            items = items[start : end + 1]

        return FakeResponse(items, count=len(items))


class FakeSupabase:
    def __init__(self):
        self.lakes = [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "name": "Lago activo",
                "region": "Lima",
                "description": "Activo",
                "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "name": "Lago inactivo",
                "region": "Arequipa",
                "description": "Inactivo",
                "geom": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
                "status": "inactive",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
        ]

    def table(self, table_name):
        return FakeTable(self, table_name)


@pytest.fixture
def client_with_authorized_lakes(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(lakes_module, "supabase", fake_db)

    def fake_authenticated_admin():
        return {"user_metadata": {"role": "administrador"}}

    app.dependency_overrides[auth.verify_supabase_jwt] = fake_authenticated_admin

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


@pytest.fixture
def client_with_unauthorized_lakes(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(lakes_module, "supabase", fake_db)

    def fake_authenticated_user():
        return {"user_metadata": {"role": "usuario"}}

    app.dependency_overrides[auth.verify_supabase_jwt] = fake_authenticated_user

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
    assert data["id"] == lake_id
    assert data["name"] == "Lago activo"
    assert data["status"] == "active"


def test_create_lake_requires_permission_and_persists(client_with_authorized_lakes):
    payload = {
        "name": "Lago nuevo",
        "region": "Cusco",
        "description": "Lago recién creado",
        "geom": {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 0]]]},
    }

    response = client_with_authorized_lakes.post("/api/v1/lakes", json=payload)

    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Lago nuevo"
    assert created["status"] == "active"

    persisted = client_with_authorized_lakes.get(f"/api/v1/lakes/{created['id']}")
    assert persisted.status_code == 200
    assert persisted.json()["name"] == "Lago nuevo"


def test_update_lake_changes_name_and_persists(client_with_authorized_lakes):
    lake_id = "11111111-1111-1111-1111-111111111111"
    payload = {"name": "Nombre actualizado", "description": "Descripción actualizada"}

    response = client_with_authorized_lakes.patch(f"/api/v1/lakes/{lake_id}", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nombre actualizado"
    assert data["description"] == "Descripción actualizada"

    persisted = client_with_authorized_lakes.get(f"/api/v1/lakes/{lake_id}")
    assert persisted.status_code == 200
    assert persisted.json()["name"] == "Nombre actualizado"


def test_delete_lake_soft_deletes_and_excludes_from_list(client_with_authorized_lakes):
    lake_id = "11111111-1111-1111-1111-111111111111"

    response = client_with_authorized_lakes.delete(f"/api/v1/lakes/{lake_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "inactive"

    after_delete = client_with_authorized_lakes.get(f"/api/v1/lakes/{lake_id}")
    assert after_delete.status_code == 200
    assert after_delete.json()["status"] == "inactive"

    list_response = client_with_authorized_lakes.get("/api/v1/lakes")
    assert list_response.status_code == 200
    assert all(item["id"] != lake_id for item in list_response.json()["items"])


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


@pytest.mark.parametrize(
    "database_point",
    [
        "POINT(-72.22 -39.28)",
        {"type": "Point", "coordinates": [-72.22, -39.28]},
    ],
)
def test_get_lake_stations_returns_geojson_point(monkeypatch, database_point):
    lake_id = "11111111-1111-1111-1111-111111111111"
    station_row = {
        "id": "33333333-3333-3333-3333-333333333333",
        "lake_id": lake_id,
        "code": "ST-01",
        "name": "Estación de prueba",
        "point": database_point,
        "description": None,
        "status": "active",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

    class Query:
        def __init__(self, table_name):
            self.table_name = table_name
            self.filters = {}

        def select(self, *args, **kwargs):
            return self

        def eq(self, field, value):
            self.filters[field] = value
            return self

        def execute(self):
            if self.table_name == "lakes":
                return FakeResponse([{"id": lake_id}])
            matches = all(
                str(station_row.get(field)) == str(value)
                for field, value in self.filters.items()
            )
            return FakeResponse([station_row] if matches else [])

    class Database:
        def table(self, table_name):
            return Query(table_name)

    monkeypatch.setattr(repositories_module, "supabase", Database())

    response = TestClient(app).get(f"/api/v1/lakes/{lake_id}/stations")

    assert response.status_code == 200
    assert response.json()[0]["point"] == {
        "type": "Point",
        "coordinates": [-72.22, -39.28],
    }


def test_get_lake_stations_documents_station_response_model():
    operation = app.openapi()["paths"]["/api/v1/lakes/{lake_id}/stations"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert response_schema["type"] == "array"
    assert response_schema["items"]["$ref"] == "#/components/schemas/StationOut"
