from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

import domain.execution.router as execution_module
from app.auth import verify_supabase_jwt
from app.config import settings
from app.main import app

USER_ID = str(uuid4())
ORGANIZATION_ID = str(uuid4())
JOB_ID = str(uuid4())
DATASET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VERSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
INTERNAL_HEADERS = {"X-Internal-Token": "test-secret-token"}
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


class FakeDatabaseError(Exception):
    def __init__(self, code):
        self.code = code


class FakeQuery:
    def __init__(self, database, schema_name, table_name):
        self.database = database
        self.schema_name = schema_name
        self.table_name = table_name
        self.filters = {}
        self.insert_data = None

    def select(self, _columns):
        return self

    def insert(self, data):
        self.insert_data = data
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        if self.database.failure:
            raise FakeDatabaseError(self.database.failure)

        if self.schema_name == "dataset" and self.table_name == "versions":
            rows = [
                version
                for version in self.database.versions
                if all(
                    str(version.get(key)) == str(value)
                    for key, value in self.filters.items()
                )
            ]
            return SimpleNamespace(data=rows)

        if self.table_name == "scientific_jobs":
            if self.insert_data is not None:
                job = {
                    **self.insert_data,
                    "id": JOB_ID,
                    "result": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
                self.database.jobs.append(job)
                return SimpleNamespace(data=[job])

            rows = [
                job
                for job in self.database.jobs
                if all(
                    str(job.get(key)) == str(value)
                    for key, value in self.filters.items()
                )
            ]
            return SimpleNamespace(data=rows)

        if self.table_name == "memberships":
            is_matching_membership = (
                self.database.membership
                and self.filters.get("user_id") == USER_ID
                and self.filters.get("organization_id") == ORGANIZATION_ID
                and self.filters.get("status") == "active"
            )
            rows = [{"id": str(uuid4())}] if is_matching_membership else []
            return SimpleNamespace(data=rows)

        raise AssertionError(f"Unexpected table: {self.table_name}")


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
        self.jobs = []
        self.membership = True
        self.failure = None

    def schema(self, schema_name):
        return SimpleNamespace(
            table=lambda table_name: FakeQuery(self, schema_name, table_name)
        )

    def table(self, table_name):
        return FakeQuery(self, None, table_name)


@pytest.fixture
def execution_client(monkeypatch):
    settings.internal_service_token = SecretStr("test-secret-token")
    database = FakeDatabase()
    monkeypatch.setattr(execution_module, "supabase", database)
    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: {"sub": USER_ID},
    )
    yield TestClient(app), database
    app.dependency_overrides.clear()


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
    payload = {
        "job_type": "estimation",
        "organization_id": ORGANIZATION_ID,
        "config": {"model_id": "model_v1", "scene_id": "scene_001"},
    }

    response = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["job_id"] in data["status_url"]
    assert database.jobs[0]["organization_id"] == ORGANIZATION_ID


def test_get_job_status_returns_200_for_organization_member(execution_client):
    client, database = execution_client
    database.jobs.append(
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
    database.jobs.append(
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
    database.jobs.append(
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


def test_create_execution_job_rejects_invalid_payload(execution_client):
    client, _database = execution_client
    invalid_payload = {
        "job_type": "training",
        "organization_id": ORGANIZATION_ID,
        "config": {"invalid_field": 123},
    }

    response = client.post(
        "/api/v1/executions/",
        json=invalid_payload,
        headers=INTERNAL_HEADERS,
    )

    assert response.status_code == 422


def test_create_execution_job_rejects_without_internal_token(execution_client):
    client, _database = execution_client
    payload = {
        "job_type": "estimation",
        "organization_id": ORGANIZATION_ID,
        "config": {"model_id": "model_v1", "scene_id": "scene_001"},
    }

    response = client.post("/api/v1/executions/", json=payload)

    assert response.status_code == 401
    assert response.json()["message"] == "Autenticación interna requerida."


def test_training_requires_a_published_dataset_version(execution_client):
    client, database = execution_client
    database.versions[0]["state"] = "APPROVED"

    response = client.post(
        "/api/v1/executions/", json=training_payload(), headers=INTERNAL_HEADERS
    )

    assert response.status_code == 409
    assert response.json()["message"] == "Solo se pueden entrenar versiones publicadas."
    assert database.jobs == []


def test_training_rejects_an_unknown_version(execution_client):
    client, database = execution_client
    payload = training_payload(version_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd")

    response = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró la versión del dataset."
    assert database.jobs == []


def test_training_requires_a_version_id(execution_client):
    client, _database = execution_client
    payload = training_payload()
    payload["config"].pop("version_id")

    response = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 422


def test_training_requires_dataset_id_to_be_a_uuid(execution_client):
    client, _database = execution_client
    payload = training_payload(dataset_id="id-invalido")

    response = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 422


def test_training_requires_version_to_belong_to_dataset(execution_client):
    client, database = execution_client
    payload = training_payload(dataset_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc")

    response = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 422
    assert response.json()["message"] == "La versión no pertenece al dataset indicado."
    assert database.jobs == []


def test_training_is_persisted_as_queued_and_returns_202(execution_client):
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
    assert len(database.jobs) == 1
    assert database.jobs[0]["status"] == "queued"
    assert database.jobs[0]["job_type"] == "training"


def test_create_execution_job_maps_postgrest_errors(execution_client):
    client, database = execution_client
    database.failure = "23503"
    payload = {
        "job_type": "estimation",
        "organization_id": ORGANIZATION_ID,
        "config": {"model_id": "model_v1", "scene_id": "scene_001"},
    }

    response = client.post(
        "/api/v1/executions/", json=payload, headers=INTERNAL_HEADERS
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No existe la organización asociada al trabajo."
