import hashlib
import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from app import auth
from app import imports as imports_module
from app.main import app


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeStorageBucket:
    def __init__(self, storage):
        self.storage = storage

    def upload(self, path, content, file_options):
        self.storage[path] = (content, file_options)
        return {"Key": path}


class FakeStorage:
    def __init__(self):
        self.files = {}

    def from_(self, bucket_name):
        assert bucket_name == "imports"
        return FakeStorageBucket(self.files)


class FakeTable:
    def __init__(self, database):
        self.database = database
        self.filters = {}
        self.insert_payload = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def limit(self, _limit):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.insert_payload is not None:
            for field in ("checksum", "idempotency_key"):
                value = self.insert_payload.get(field)
                if value and any(row.get(field) == value for row in self.database.rows):
                    raise APIError({"code": "23505", "message": "unique violation"})
            row = {
                **self.insert_payload,
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
            }
            self.database.rows.append(row)
            return FakeResponse([row])

        rows = [
            row
            for row in self.database.rows
            if all(row.get(key) == value for key, value in self.filters.items())
        ]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.rows = []
        self.storage = FakeStorage()

    def table(self, _table_name):
        return FakeTable(self)


@pytest.fixture
def import_client(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(imports_module, "supabase", fake_db)
    monkeypatch.setitem(
        app.dependency_overrides,
        auth.verify_supabase_jwt,
        lambda: {"sub": "11111111-1111-1111-1111-111111111111"},
    )
    return TestClient(app), fake_db


def test_create_import_uploads_file_and_returns_record(import_client):
    client, fake_db = import_client

    response = client.post(
        "/api/v1/imports",
        files={"file": ("stations.csv", b"id,name\n1,North\n", "text/csv")},
        headers={"X-Idempotency-Key": "upload-1"},
    )

    assert response.status_code == 201
    record = response.json()
    assert record["filename"] == "stations.csv"
    content = b"id,name\n1,North\n"
    assert record["checksum"] == hashlib.sha256(content).hexdigest()
    assert record["file_size"] == len(content)
    assert record["status"] == "pending"
    assert "storage_path" not in record
    assert len(fake_db.rows) == 1
    assert len(fake_db.storage.files) == 1


def test_same_file_and_key_returns_existing_import(import_client):
    client, fake_db = import_client
    files = {"file": ("stations.csv", b"id,name\n1,North\n", "text/csv")}
    headers = {"X-Idempotency-Key": "upload-1"}

    first = client.post("/api/v1/imports", files=files, headers=headers)
    second = client.post("/api/v1/imports", files=files, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(fake_db.rows) == 1


def test_reusing_key_for_different_file_returns_conflict(import_client):
    client, fake_db = import_client
    headers = {"X-Idempotency-Key": "upload-1"}
    client.post(
        "/api/v1/imports",
        files={"file": ("stations.csv", b"id,name\n1,North\n", "text/csv")},
        headers=headers,
    )

    response = client.post(
        "/api/v1/imports",
        files={"file": ("stations.csv", b"id,name\n2,South\n", "text/csv")},
        headers=headers,
    )

    assert response.status_code == 409
    assert len(fake_db.rows) == 1


def test_same_checksum_without_idempotency_header_is_deduplicated(import_client):
    client, fake_db = import_client
    file = {"file": ("stations.csv", b"id,name\n1,North\n", "text/csv")}

    first = client.post("/api/v1/imports", files=file)
    second = client.post("/api/v1/imports", files=file)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(fake_db.rows) == 1


def test_empty_file_is_rejected(import_client):
    client, fake_db = import_client

    response = client.post(
        "/api/v1/imports", files={"file": ("empty.csv", b"", "text/csv")}
    )

    assert response.status_code == 400
    assert not fake_db.rows


def test_import_requires_authentication(import_client):
    client, fake_db = import_client
    override = app.dependency_overrides.pop(auth.verify_supabase_jwt)
    try:
        response = client.post(
            "/api/v1/imports",
            files={"file": ("stations.csv", b"id,name\n1,North\n", "text/csv")},
        )
    finally:
        app.dependency_overrides[auth.verify_supabase_jwt] = override

    assert response.status_code == 401
    assert not fake_db.rows