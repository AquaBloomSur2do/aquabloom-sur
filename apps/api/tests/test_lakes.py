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


class FakeTable:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []
        self.payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def neq(self, column, value):
        self.filters.append(("neq", column, value))
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        rows = self.rows
        for op, column, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if str(row.get(column)) == str(value)]
            elif op == "neq":
                rows = [row for row in rows if str(row.get(column)) != str(value)]

        if self.payload is not None:
            updated = []
            for row in self.rows:
                if all(
                    str(row.get(column)) == str(value)
                    for op, column, value in self.filters
                ):
                    row = {**row, **self.payload}
                updated.append(row)
            self.rows = updated
            self.payload = None
            return SimpleNamespace(data=updated)

        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, rows):
        self.rows = list(rows)

    def table(self, _name):
        return FakeTable(self.rows)


def build_token(permissions=None):
    payload = {
        "sub": "123e4567-e89b-12d3-a456-426614174000",
        "email": "user@example.com",
        "aud": "authenticated",
        "iss": f"{settings.supabase_url}/auth/v1",
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
            {"id": lake_id, "name": "Activo", "status": "active"},
            {"id": other_id, "name": "Inactivo", "status": "inactive"},
        ]
    )
    monkeypatch.setattr("app.database.supabase", fake_client)
    import app.lakes as lakes_module

    monkeypatch.setattr(lakes_module, "supabase", fake_client)

    client = TestClient(app)
    response = client.get("/api/v1/lakes")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data] == [lake_id]


def test_delete_lake_requires_catalog_disable_permission(monkeypatch):
    settings.supabase_jwt_secret = "test-secret"
    settings.supabase_url = "https://example.supabase.co"
    lake_id = "123e4567-e89b-12d3-a456-426614174000"
    fake_client = FakeSupabase([{"id": lake_id, "name": "Activo", "status": "active"}])
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
    fake_client = FakeSupabase([{"id": lake_id, "name": "Activo", "status": "active"}])
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
