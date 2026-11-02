import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import SecretStr

import domain.execution.router as execution_module
from app.auth import verify_supabase_jwt
from app.config import settings
from app.main import app

USER_ID = str(uuid.uuid4())
ORGANIZATION_ID = str(uuid.uuid4())
JOB_ID = str(uuid.uuid4())
DATASET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VERSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
INTERNAL_HEADERS = {"X-Internal-Token": "test-secret-token"}
AUTH_HEADERS = {"Authorization": "Bearer test-jwt"}


class FakeDatabaseError(Exception):
    def __init__(self, code):
        self.code = code


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, database, schema_name, table_name):
        self.database = database
        self.schema_name = schema_name
        self.table_name = table_name
        self.filters = {}
        self.insert_payload = None
        self.update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters[column] = str(value)
        return self

    def limit(self, _limit):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def execute(self):
        if self.database.failure:
            raise FakeDatabaseError(self.database.failure)

        if self.schema_name == "dataset" and self.table_name == "versions":
            rows = [
                version
                for version in self.database.versions
                if all(
                    str(version.get(key)) == value
                    for key, value in self.filters.items()
                )
            ]
            return FakeResponse(rows)

        if self.table_name == "memberships":
            matching_membership = (
                self.database.membership
                and self.filters.get("user_id") == USER_ID
                and self.filters.get("organization_id") == ORGANIZATION_ID
                and self.filters.get("status") == "active"
            )
            return FakeResponse([{"id": str(uuid.uuid4())}] if matching_membership else [])

        if self.table_name != "scientific_jobs":
            raise AssertionError(f"Unexpected table: {self.table_name}")

        if self.update_payload is not None:
            updated_rows = []
            for row in self.database.rows:
                if all(
                    str(row.get(column)) == value
                    for column, value in self.filters.items()
                ):
                    row.update(self.update_payload)
                    updated_rows.append(row)
            return FakeResponse(updated_rows)

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
            if all(str(row.get(column)) == value for column, value in self.filters.items())
        ]
        return FakeResponse(rows)


class FakeDatabase:
    def __init__(self):
        self.versions = [
            {
                "id": VERSION_ID,
                "dataset_id": DATASET_ID,
                "state": "PUBLISHED",
                "status": "PUBLISHED",
            }
        ]
        self.rows = []
        self.membership = True
        self.failure = None
        self.race_on_insert = False

    def schema(self, schema_name):
        return SimpleNamespace(
            table=lambda table_name: FakeQuery(self, schema_name, table_name)
        )

    def table(self, table_name):
        return FakeQuery(self, None, table_name)


@pytest.fixture
def execution_client(monkeypatch):
    monkeypatch.setattr(
        settings, "internal_service_token", SecretStr("test-secret-token")
    )
    database = FakeDatabase()
    monkeypatch.setattr(execution_module, "supabase", database)
    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: {"sub": USER_ID},
    )
    yield TestClient(app), database
    app.dependency_overrides.pop(verify_supabase_jwt, None)


def estimation_payload(model_id="model_v1", scene_id="scene_001"):
    return {
        "job_type": "estimation",
        "organization_id": ORGANIZATION_ID,
        "config": {"model_id": model_id, "scene_id": scene_id},
    }


def training_payload(version_id=VERSION_ID, dataset_id=DATASET_ID):
    return {
        "job_type": "training",
        "organization_id": ORGANIZATION_ID,
        "config": {
            "dataset_id": dataset_id,
            "version_id": version_id,
            "epochs": 50,
            "learning_rate": 0.01,
        },
    }


def test_create_execution_job_returns_202(execution_client):
    client, database = execution_client
    response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["job_id"] in data["status_url"]
    assert database.rows[0]["organization_id"] == ORGANIZATION_ID
    assert database.rows[0]["status"] == "completed"


def test_get_job_status_returns_200_for_organization_member(execution_client):
    client, database = execution_client
    database.rows.append(
        {
            "id": JOB_ID,
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "completed",
            "config": {"epochs": 50},
            "result": {"accuracy": 0.95},
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    response = client.get(
        f"/api/v1/executions/{JOB_ID}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == JOB_ID
    assert response.json()["status"] == "completed"
    assert response.json()["result"] == {"accuracy": 0.95}
    assert response.json()["config"] == {"epochs": 50}


def test_get_job_status_returns_403_for_another_organization(execution_client):
    client, database = execution_client
    database.membership = False
    database.rows.append(
        {
            "id": JOB_ID,
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "running",
            "config": {},
            "result": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    response = client.get(f"/api/v1/executions/{JOB_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 403


def test_get_job_status_returns_404_for_missing_job(execution_client):
    client, _database = execution_client

    response = client.get(f"/api/v1/executions/{JOB_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_get_job_status_rejects_job_without_organization(execution_client):
    client, database = execution_client
    database.rows.append(
        {
            "id": JOB_ID,
            "job_type": "training",
            "status": "running",
            "config": {},
            "result": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    response = client.get(f"/api/v1/executions/{JOB_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_get_job_status_rejects_invalid_user_id(execution_client, monkeypatch):
    client, database = execution_client
    database.rows.append(
        {
            "id": JOB_ID,
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "running",
            "config": {},
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: {"sub": "not-a-uuid"},
    )

    response = client.get(f"/api/v1/executions/{JOB_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 401


def test_get_job_status_returns_404_for_invalid_id(execution_client):
    client, _database = execution_client
    missing_job_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(
        f"/api/v1/executions/{missing_job_id}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404


def test_create_execution_job_rejects_invalid_payload(execution_client):
    client, _database = execution_client
    response = client.post(
        "/api/v1/executions/",
        json={
            "job_type": "training",
            "organization_id": ORGANIZATION_ID,
            "config": {"invalid_field": 123},
        },
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 422


def test_create_execution_job_rejects_without_internal_token(execution_client):
    client, _database = execution_client

    response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Autenticación interna requerida."


def test_same_idempotency_key_and_payload_returns_same_job(execution_client):
    client, database = execution_client
    headers = {**INTERNAL_HEADERS, "X-Idempotency-Key": "test-idem-key-001"}
    payload = estimation_payload()

    first = client.post("/api/v1/executions/", json=payload, headers=headers)
    second = client.post("/api/v1/executions/", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["job_id"] == first.json()["job_id"]
    assert len(database.rows) == 1


def test_reusing_idempotency_key_with_different_payload_returns_conflict(
    execution_client,
):
    client, database = execution_client
    headers = {**INTERNAL_HEADERS, "X-Idempotency-Key": "test-idem-key-002"}
    first = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers=headers,
    )
    second = client.post(
        "/api/v1/executions/",
        json=estimation_payload(model_id="model_v2", scene_id="scene_002"),
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 409
    assert len(database.rows) == 1


def test_concurrent_idempotent_insert_returns_existing_job(execution_client):
    client, database = execution_client
    database.race_on_insert = True
    headers = {**INTERNAL_HEADERS, "X-Idempotency-Key": "test-idem-race"}
    response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers=headers,
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == database.rows[0]["id"]
    assert len(database.rows) == 1


def test_requests_without_idempotency_key_create_distinct_jobs(execution_client):
    client, database = execution_client
    payload = estimation_payload(scene_id="scene_003")
    first = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )
    second = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(database.rows) == 2


def test_empty_idempotency_key_is_rejected(execution_client):
    client, _database = execution_client
    headers = {**INTERNAL_HEADERS, "X-Idempotency-Key": "   "}

    response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers=headers,
    )

    assert response.status_code == 422


def test_execution_job_handles_internal_exception(execution_client):
    client, database = execution_client
    response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(scene_id="scene_fail"),
        headers=INTERNAL_HEADERS,
    )
    job_id = response.json()["job_id"]
    job = next(row for row in database.rows if row["id"] == job_id)

    assert response.status_code == 202
    assert job["status"] == "failed"
    assert (
        job["error_message"]
        == "Excepción interna: Fallo al procesar los tensores de la escena."
    )


def test_execution_job_handles_timeout_exceeded(execution_client, monkeypatch):
    client, database = execution_client
    monkeypatch.setattr(execution_module, "JOB_TIMEOUT_SECONDS", 0.1)
    response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(scene_id="scene_timeout"),
        headers=INTERNAL_HEADERS,
    )
    job_id = response.json()["job_id"]
    job = next(row for row in database.rows if row["id"] == job_id)

    assert response.status_code == 202
    assert job["status"] == "failed"
    assert "Timeout de 0.1s" in job["error_message"]


def test_training_requires_a_published_dataset_version(execution_client):
    client, database = execution_client
    database.versions[0]["state"] = "APPROVED"
    response = client.post(
        "/api/v1/executions/",
        json=training_payload(),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 409
    assert response.json()["message"] == "Solo se pueden entrenar versiones publicadas."
    assert database.rows == []


def test_training_rejects_an_unknown_version(execution_client):
    client, database = execution_client
    response = client.post(
        "/api/v1/executions/",
        json=training_payload(version_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró la versión del dataset."
    assert database.rows == []


def test_training_requires_a_version_id(execution_client):
    client, _database = execution_client
    payload = training_payload()
    payload["config"].pop("version_id")
    response = client.post(
        "/api/v1/executions/",
        json=payload,
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 422


def test_training_requires_dataset_id_to_be_a_uuid(execution_client):
    client, _database = execution_client
    response = client.post(
        "/api/v1/executions/",
        json=training_payload(dataset_id="id-invalido"),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 422


def test_training_requires_version_to_belong_to_dataset(execution_client):
    client, database = execution_client
    response = client.post(
        "/api/v1/executions/",
        json=training_payload(dataset_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 422
    assert response.json()["message"] == "La versión no pertenece al dataset indicado."
    assert database.rows == []


def test_training_is_persisted_and_processed(execution_client):
    client, database = execution_client
    response = client.post(
        "/api/v1/executions/",
        json=training_payload(),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["status_url"] == f"/api/v1/executions/{data['job_id']}"
    assert len(database.rows) == 1
    assert database.rows[0]["status"] == "completed"
    assert database.rows[0]["job_type"] == "training"
    assert database.rows[0]["organization_id"] == ORGANIZATION_ID


def test_create_execution_job_maps_postgrest_errors(execution_client):
    client, database = execution_client
    database.failure = "23503"

    response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No existe la organización asociada al trabajo."
