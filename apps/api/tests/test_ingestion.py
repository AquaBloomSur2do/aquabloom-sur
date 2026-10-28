import os
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from app import auth
from app.main import app
from ingestion.application import endpoints as ingestion_module


@pytest.fixture
def ingestion_client(monkeypatch):
    original_import_id = uuid.uuid4()
    supabase_mock = MagicMock()
    imports_table = MagicMock()
    prepared_inputs_table = MagicMock()
    supabase_mock.table.side_effect = {
        "imports": imports_table,
        "prepared_inputs": prepared_inputs_table,
    }.get
    imports_table.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
        SimpleNamespace(data=[{"id": str(original_import_id)}])
    )
    prepared_inputs_table.insert.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": str(uuid.uuid4()),
                "original_import_id": str(original_import_id),
                "source_key": "S2A_scene_001",
                "metadata": {"satellite": "Sentinel-2", "cloud_cover": 4.2},
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]
    )
    monkeypatch.setattr(ingestion_module, "supabase", supabase_mock)
    monkeypatch.setitem(
        app.dependency_overrides,
        auth.verify_supabase_jwt,
        lambda: {"sub": "11111111-1111-1111-1111-111111111111"},
    )
    return TestClient(app), prepared_inputs_table, original_import_id


def test_register_prepared_input_succeeds(ingestion_client):
    client, prepared_inputs_table, original_import_id = ingestion_client
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
    prepared_inputs_table.insert.assert_called_once_with(
        {
            "original_import_id": str(original_import_id),
            "source_key": "S2A_scene_001",
            "metadata": metadata,
        }
    )


def test_register_duplicate_source_key_returns_conflict(ingestion_client):
    client, prepared_inputs_table, original_import_id = ingestion_client
    prepared_inputs_table.insert.return_value.execute.side_effect = APIError(
        {
            "code": "23505",
            "details": {"code": "23505"},
            "message": "duplicate key",
        }
    )

    response = client.post(
        "/api/v1/ingestion/prepared",
        json={
            "original_import_id": str(original_import_id),
            "source_key": "S2A_scene_001",
            "metadata": {"satellite": "Sentinel-2"},
        },
    )

    assert response.status_code == 409


def test_register_missing_original_import_returns_not_found(ingestion_client):
    client, prepared_inputs_table, original_import_id = ingestion_client
    prepared_inputs_table.insert.return_value.execute.side_effect = APIError(
        {
            "code": "23503",
            "details": {"code": "23503"},
            "message": "foreign key violation",
        }
    )

    response = client.post(
        "/api/v1/ingestion/prepared",
        json={
            "original_import_id": str(original_import_id),
            "source_key": "S2A_scene_001",
            "metadata": {"satellite": "Sentinel-2"},
        },
    )

    assert response.status_code == 404
