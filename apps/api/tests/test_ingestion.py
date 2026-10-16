import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from app import auth
from app.main import app
from ingestion.application import endpoints as ingestion_module


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.filters = {}
        self.insert_payload = None

    def select(self, *_args, **_kwargs):
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
        rows = self.database.rows[self.table_name]
        if self.insert_payload is not None:
            if self.table_name == "prepared_inputs":
                original_import_id = self.insert_payload["original_import_id"]
                if not any(
                    row["id"] == original_import_id
                    for row in self.database.rows["imports"]
                ):
                    raise APIError({"code": "23503", "message": "foreign key violation"})
                source_key = self.insert_payload["source_key"]
                if any(row["source_key"] == source_key for row in rows):
                    raise APIError({"code": "23505", "message": "unique violation"})

            row = {
                **self.insert_payload,
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
            }
            rows.append(row)
            return FakeResponse([row])

        selected = [
            row
            for row in rows
            if all(row.get(field) == value for field, value in self.filters.items())
        ]
        return FakeResponse(selected)


class FakeSupabase:
    def __init__(self, original_import_ids):
        self.rows = {
            "imports": [{"id": str(import_id)} for import_id in original_import_ids],
            "prepared_inputs": [],
        }

    def table(self, table_name):
        return FakeTable(self, table_name)


@pytest.fixture
def ingestion_client(monkeypatch):
    original_import_id = uuid.uuid4()
    fake_db = FakeSupabase([original_import_id])
    monkeypatch.setattr(ingestion_module, "supabase", fake_db)
    monkeypatch.setitem(
        app.dependency_overrides,
        auth.verify_supabase_jwt,
        lambda: {"sub": "11111111-1111-1111-1111-111111111111"},
    )
    return TestClient(app), fake_db, original_import_id


def test_register_prepared_input_keeps_original_reference_and_metadata(ingestion_client):
    client, fake_db, original_import_id = ingestion_client
    metadata = {"satellite": "Sentinel-2", "cloud_cover": 4.2}

    response = client.post(
        "/api/v1/ingestion/prepared",
        json={
            "original_import_id": str(original_import_id),
            "source_key": "S2A_scene_001",
            "metadata": metadata,
        },
    )

    assert response.status_code == 201
    assert response.json()["original_import_id"] == str(original_import_id)
    assert response.json()["source_key"] == "S2A_scene_001"
    assert response.json()["metadata"] == metadata
    assert len(fake_db.rows["prepared_inputs"]) == 1


def test_register_duplicate_source_key_returns_conflict(ingestion_client):
    client, fake_db, original_import_id = ingestion_client
    payload = {
        "original_import_id": str(original_import_id),
        "source_key": "S2A_scene_001",
        "metadata": {"satellite": "Sentinel-2"},
    }

    first = client.post("/api/v1/ingestion/prepared", json=payload)
    second = client.post(
        "/api/v1/ingestion/prepared",
        json={**payload, "metadata": {"satellite": "Sentinel-2B"}},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(fake_db.rows["prepared_inputs"]) == 1
