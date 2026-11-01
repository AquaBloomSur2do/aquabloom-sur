import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import SecretStr

from app.config import settings
from app.main import app
from domain.execution import router as execution_router

settings.internal_service_token = SecretStr("test-secret-token")

HEADERS = {"X-Internal-Token": "test-secret-token"}
client = TestClient(app)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, database):
        self.database = database
        self.filters = {}
        self.insert_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _limit):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def execute(self):
        if self.insert_payload is not None:
            idempotency_key = self.insert_payload.get("idempotency_key")
            if idempotency_key and self.database.race_on_insert:
                self.database.race_on_insert = False
                raced_row = {
                    **self.insert_payload,
                    "id": str(uuid.uuid4()),
                    "created_at": datetime.now(UTC).isoformat(),
                    "result": None,
                }
                self.database.rows.append(raced_row)
                raise APIError(
                    {"code": "23505", "message": "unique constraint violation"}
                )
            if idempotency_key and any(
                row.get("idempotency_key") == idempotency_key
                for row in self.database.rows
            ):
                raise APIError(
                    {"code": "23505", "message": "unique constraint violation"}
                )

            row = {
                **self.insert_payload,
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
                "result": None,
            }
            self.database.rows.append(row)
            return FakeResponse([row])

        rows = [
            row
            for row in self.database.rows
            if all(row.get(column) == value for column, value in self.filters.items())
        ]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self):
        self.rows = []
        self.race_on_insert = False

    def table(self, _table_name):
        return FakeQuery(self)


@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
    database = FakeSupabase()
    monkeypatch.setattr(execution_router, "supabase", database)
    return database


def estimation_payload(model_id="model_v1", scene_id="scene_001"):
    return {
        "job_type": "estimation",
        "config": {"model_id": model_id, "scene_id": scene_id},
    }


def test_create_execution_job_returns_202():
    response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=HEADERS
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert data["status_url"] == f"/api/v1/executions/{data['job_id']}"


def test_get_job_status_returns_200(mock_supabase):
    payload = {
        "job_type": "training",
        "config": {
            "dataset_id": "dataset_123",
            "epochs": 50,
            "learning_rate": 0.01,
        },
    }
    post_response = client.post(
        "/api/v1/executions/", json=payload, headers=HEADERS
    )
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    response = client.get(f"/api/v1/executions/{job_id}", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
    assert response.json()["status"] == "pending"
    assert len(mock_supabase.rows) == 1


def test_get_job_status_returns_404_for_invalid_id():
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/executions/{fake_uuid}", headers=HEADERS)

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."


def test_create_execution_job_invalid_payload():
    response = client.post(
        "/api/v1/executions/",
        json={"job_type": "training", "config": {"invalid_field": 123}},
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_create_execution_job_rejects_without_token():
    response = client.post("/api/v1/executions/", json=estimation_payload())

    assert response.status_code == 401
    assert response.json()["message"] == "Autenticación interna requerida."


def test_same_idempotency_key_and_payload_returns_same_job(mock_supabase):
    headers = {**HEADERS, "X-Idempotency-Key": "test-idem-key-001"}
    payload = estimation_payload()

    first = client.post("/api/v1/executions/", json=payload, headers=headers)
    second = client.post("/api/v1/executions/", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json() == first.json()
    assert len(mock_supabase.rows) == 1


def test_reusing_idempotency_key_with_different_payload_returns_conflict(
    mock_supabase,
):
    headers = {**HEADERS, "X-Idempotency-Key": "test-idem-key-002"}
    first = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=headers
    )
    second = client.post(
        "/api/v1/executions/",
        json=estimation_payload(model_id="model_v2", scene_id="scene_002"),
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 409
    assert len(mock_supabase.rows) == 1


def test_concurrent_idempotent_insert_returns_existing_job(mock_supabase):
    mock_supabase.race_on_insert = True
    headers = {**HEADERS, "X-Idempotency-Key": "test-idem-race"}

    response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=headers
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == mock_supabase.rows[0]["id"]
    assert len(mock_supabase.rows) == 1


def test_requests_without_idempotency_key_create_distinct_jobs(mock_supabase):
    payload = estimation_payload(scene_id="scene_003")

    first = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    second = client.post("/api/v1/executions/", json=payload, headers=HEADERS)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(mock_supabase.rows) == 2


def test_empty_idempotency_key_is_rejected():
    headers = {**HEADERS, "X-Idempotency-Key": "   "}
    response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=headers
    )

    assert response.status_code == 422
