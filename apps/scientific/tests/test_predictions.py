import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import SecretStr

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.scientific.app.core.config import settings
from apps.scientific.app.domains.prediction import controller_prediction
from apps.scientific.app.main import app

client = TestClient(app)
HEADERS = {"X-Internal-Token": "test-secret-token"}
MODEL_VERSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SCENE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@pytest.fixture(autouse=True)
def internal_service_token(monkeypatch):
    monkeypatch.setattr(
        settings,
        "internal_service_token",
        SecretStr("test-secret-token"),
    )


class FakePredictionDatabase:
    def __init__(self):
        self.rows = []
        self.payload = None
        self.fail_on_insert = False

    def schema(self, schema_name):
        assert schema_name == "scientific"
        return self

    def table(self, table_name):
        assert table_name == "predictions"
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.fail_on_insert:
            raise APIError({"code": "23503", "message": "foreign key violation"})

        row = {
            **self.payload,
            "id": str(uuid.uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.rows.append(row)
        return SimpleNamespace(data=[row])


def prediction_payload():
    return {
        "model_version_id": MODEL_VERSION_ID,
        "scene_id": SCENE_ID,
        "result": {"chlorophyll_a": 12.5, "unit": "ug/L"},
        "rules": [{"rule_id": "cloud-mask", "version": "1.0"}],
    }


def test_create_prediction_appends_each_result(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    payload = prediction_payload()

    first = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)
    second = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["created_at"] != "" and second.json()["created_at"] != ""
    assert len(database.rows) == 2
    assert database.rows[0]["result"] == payload["result"]
    assert database.rows[0]["rules"] == [
        {"rule_id": "cloud-mask", "version": "1.0", "parameters": {}}
    ]
    assert database.rows[0]["model_version_id"] == MODEL_VERSION_ID
    assert database.rows[0]["scene_id"] == SCENE_ID


def test_create_prediction_requires_internal_token(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)

    response = client.post("/api/v1/predictions/", json=prediction_payload())

    assert response.status_code == 401
    assert not database.rows


def test_create_prediction_rejects_extra_fields_at_each_level(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    payload = prediction_payload()
    payload["unexpected"] = True
    payload["rules"][0]["unexpected"] = True

    response = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)

    assert response.status_code == 422
    assert not database.rows


def test_create_prediction_returns_not_found_for_missing_scene(monkeypatch):
    database = FakePredictionDatabase()
    database.fail_on_insert = True
    monkeypatch.setattr(controller_prediction, "supabase", database)

    response = client.post(
        "/api/v1/predictions/", json=prediction_payload(), headers=HEADERS
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró la escena especificada."
