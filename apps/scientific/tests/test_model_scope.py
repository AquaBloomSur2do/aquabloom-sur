import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import SecretStr

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.api.app.core.config import settings as api_settings
from apps.scientific.app.domains import model_scope
from apps.scientific.app.main import app

api_settings.internal_service_token = SecretStr("test-secret-token")

client = TestClient(app)
HEADERS = {"X-Internal-Token": "test-secret-token"}
LAKE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


class FakeModelScopeDatabase:
    def __init__(self):
        self.payload = None

    def table(self, table_name):
        assert table_name == "scientific_model_scopes"
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return SimpleNamespace(
            data=[
                {
                    **self.payload,
                    "id": str(uuid.uuid4()),
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ]
        )


def test_create_model_scope_persists_scope_without_validation(monkeypatch):
    database = FakeModelScopeDatabase()
    monkeypatch.setattr(
        model_scope.controller_model_scope, "supabase", database
    )
    payload = {
        "lake_id": LAKE_ID,
        "variable": "clorofila_a",
        "observed_range": {"minimum": 0.2, "maximum": 15.0},
        "experimental_condition": "muestras de verano",
    }

    response = client.post(
        "/api/v1/model-scopes/",
        json=payload,
        headers=HEADERS,
    )

    assert response.status_code == 201
    assert database.payload == {**payload, "is_validated": False}
    assert response.json()["lake_id"] == LAKE_ID
    assert response.json()["variable"] == "clorofila_a"
    assert response.json()["observed_range"] == {
        "minimum": 0.2,
        "maximum": 15.0,
    }
    assert response.json()["experimental_condition"] == "muestras de verano"
    assert response.json()["is_validated"] is False


def test_create_model_scope_rejects_validation_override(monkeypatch):
    database = FakeModelScopeDatabase()
    monkeypatch.setattr(
        model_scope.controller_model_scope, "supabase", database
    )

    response = client.post(
        "/api/v1/model-scopes/",
        json={
            "lake_id": LAKE_ID,
            "variable": "clorofila_a",
            "observed_range": {"minimum": 0.2, "maximum": 15.0},
            "experimental_condition": "muestras de verano",
            "is_validated": True,
        },
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert database.payload is None


def test_create_model_scope_rejects_reversed_observed_range(monkeypatch):
    database = FakeModelScopeDatabase()
    monkeypatch.setattr(
        model_scope.controller_model_scope, "supabase", database
    )

    response = client.post(
        "/api/v1/model-scopes/",
        json={
            "lake_id": LAKE_ID,
            "variable": "clorofila_a",
            "observed_range": {"minimum": 15.0, "maximum": 0.2},
            "experimental_condition": "muestras de verano",
        },
        headers=HEADERS,
    )

    assert response.status_code == 422
    assert database.payload is None
