
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from domain.execution import router as execution_router

# 1. Envolvemos el token en SecretStr para que coincida con el modelo de configuración
settings.internal_service_token = SecretStr("test-secret-token")

client = TestClient(app)

# 2. Definimos los headers de autorización para usar en las pruebas
HEADERS = {"X-Internal-Token": "test-secret-token"}
DATASET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VERSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


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

        if self.table_name != "scientific_jobs":
            raise AssertionError(f"Unexpected table: {self.table_name}")

        if self.insert_data is not None:
            job = {
                **self.insert_data,
                "id": str(uuid4()),
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

    def schema(self, schema_name):
        return SimpleNamespace(
            table=lambda table_name: FakeQuery(self, schema_name, table_name)
        )

    def table(self, table_name):
        return FakeQuery(self, None, table_name)


@pytest.fixture(autouse=True)
def fake_database(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(execution_router, "supabase", database)
    return database


def training_payload(version_id=VERSION_ID, dataset_id=DATASET_ID):
    return {
        "job_type": "training",
        "config": {
            "dataset_id": dataset_id,
            "version_id": version_id,
            "epochs": 50,
            "learning_rate": 0.01,
        },
    }


def test_create_execution_job_returns_202():
    payload = {
        "job_type": "estimation",
        "config": {
            "model_id": "model_v1",
            "scene_id": "scene_001",
        },
    }
    
    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"
    assert "status_url" in data
    assert data["job_id"] in data["status_url"]


def test_get_job_status_returns_200():
    payload = training_payload()
    post_response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert post_response.status_code == 202
    
    job_id = post_response.json()["job_id"]
    
    response = client.get(f"/api/v1/executions/{job_id}", headers=HEADERS)
    
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert "status" in data


def test_get_job_status_returns_404_for_invalid_id():
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/executions/{fake_uuid}", headers=HEADERS)
    
    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."


def test_create_execution_job_invalid_payload():
    invalid_payload = {
        "job_type": "training",
        "config": {
            "invalid_field": 123
        }
    }
    response = client.post("/api/v1/executions/", json=invalid_payload, headers=HEADERS)
    assert response.status_code == 422


def test_training_requires_a_published_dataset_version(fake_database):
    fake_database.versions[0]["state"] = "APPROVED"
    payload = training_payload()

    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)

    assert response.status_code == 409
    assert response.json()["message"] == "Solo se pueden entrenar versiones publicadas."
    assert fake_database.jobs == []


def test_training_rejects_an_unknown_version(fake_database):
    payload = training_payload(version_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd")

    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró la versión del dataset."
    assert fake_database.jobs == []


def test_training_requires_a_version_id():
    payload = training_payload()
    payload["config"].pop("version_id")

    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)

    assert response.status_code == 422


def test_training_requires_version_to_belong_to_dataset(fake_database):
    payload = training_payload(dataset_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc")

    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)

    assert response.status_code == 422
    assert response.json()["message"] == "La versión no pertenece al dataset indicado."
    assert fake_database.jobs == []


def test_training_is_persisted_as_pending_without_running_inline(fake_database):
    response = client.post(
        "/api/v1/executions/", json=training_payload(), headers=HEADERS
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "pending"
    assert data["status_url"] == f"/api/v1/executions/{data['job_id']}"
    assert len(fake_database.jobs) == 1
    assert fake_database.jobs[0]["status"] == "pending"
    assert fake_database.jobs[0]["job_type"] == "training"


def test_create_execution_job_rejects_without_token():
    payload = {
        "job_type": "estimation",
        "config": {
            "model_id": "model_v1",
            "scene_id": "scene_001",
        },
    }
    # Petición SIN los headers, debe ser rechazada con 401
    response = client.post("/api/v1/executions/", json=payload)
    
    assert response.status_code == 401
    assert response.json()["message"] == "Autenticación interna requerida."
