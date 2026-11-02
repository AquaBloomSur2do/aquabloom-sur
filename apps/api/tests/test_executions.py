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

from app.config import settings
from app.main import app
from domain.execution import router as execution_router

settings.internal_service_token = SecretStr("test-secret-token")
client = TestClient(app)

HEADERS = {"X-Internal-Token": "test-secret-token"}
DATASET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VERSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


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

    def select(self, *_args, **kwargs):
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
        # 1. Esquema dataset - tabla versions (S2-147)
        if self.schema_name == "dataset" and self.table_name == "versions":
            rows = [
                version
                for version in self.database.versions
                if all(str(version.get(key)) == str(value) for key, value in self.filters.items())
            ]
            return SimpleNamespace(data=rows)

        # 2. Esquema por defecto - tabla scientific_jobs (S2-150 / S2-149)
        if self.table_name != "scientific_jobs":
            raise AssertionError(f"Unexpected table: {self.table_name}")

        if self.update_payload is not None:
            updated_rows = []
            for row in self.database.rows:
                if all(str(row.get(column)) == value for column, value in self.filters.items()):
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
                raise APIError({"code": "23505", "message": "unique constraint violation"})

            if idempotency_key and any(row.get("idempotency_key") == idempotency_key for row in self.database.rows):
                raise APIError({"code": "23505", "message": "unique constraint violation"})

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
        self.rows = []  # Equivale a scientific_jobs
        self.race_on_insert = False

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


def estimation_payload(model_id="model_v1", scene_id="scene_001"):
    return {
        "job_type": "estimation",
        "config": {"model_id": model_id, "scene_id": scene_id},
    }

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


# =========================================================
# PRUEBAS S2-150 Y S2-149: IDEMPOTENCIA Y FLUJO BASE
# =========================================================

def test_create_execution_job_returns_202(fake_database):
    response = client.post("/api/v1/executions/", json=estimation_payload(), headers=HEADERS)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["status_url"] == f"/api/v1/executions/{data['job_id']}"


def test_get_job_status_returns_200(fake_database):
    post_response = client.post("/api/v1/executions/", json=estimation_payload(), headers=HEADERS)
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    response = client.get(f"/api/v1/executions/{job_id}", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "completed"
    assert len(fake_database.rows) == 1


def test_get_job_status_returns_404_for_invalid_id(fake_database):
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/executions/{fake_uuid}", headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."


def test_create_execution_job_invalid_payload(fake_database):
    response = client.post(
        "/api/v1/executions/",
        json={"job_type": "training", "config": {"invalid_field": 123}},
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_create_execution_job_rejects_without_token(fake_database):
    response = client.post("/api/v1/executions/", json=estimation_payload())
    assert response.status_code == 401
    assert response.json()["message"] == "Autenticación interna requerida."


def test_same_idempotency_key_and_payload_returns_same_job(fake_database):
    headers = {**HEADERS, "X-Idempotency-Key": "test-idem-key-001"}
    payload = estimation_payload()

    first = client.post("/api/v1/executions/", json=payload, headers=headers)
    second = client.post("/api/v1/executions/", json=payload, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["job_id"] == first.json()["job_id"]
    assert len(fake_database.rows) == 1


def test_reusing_idempotency_key_with_different_payload_returns_conflict(fake_database):
    headers = {**HEADERS, "X-Idempotency-Key": "test-idem-key-002"}
    first = client.post("/api/v1/executions/", json=estimation_payload(), headers=headers)
    second = client.post(
        "/api/v1/executions/",
        json=estimation_payload(model_id="model_v2", scene_id="scene_002"),
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 409
    assert len(fake_database.rows) == 1


def test_concurrent_idempotent_insert_returns_existing_job(fake_database):
    fake_database.race_on_insert = True
    headers = {**HEADERS, "X-Idempotency-Key": "test-idem-race"}
    response = client.post("/api/v1/executions/", json=estimation_payload(), headers=headers)

    assert response.status_code == 202
    assert response.json()["job_id"] == fake_database.rows[0]["id"]
    assert len(fake_database.rows) == 1


def test_requests_without_idempotency_key_create_distinct_jobs(fake_database):
    payload = estimation_payload(scene_id="scene_003")
    first = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    second = client.post("/api/v1/executions/", json=payload, headers=HEADERS)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(fake_database.rows) == 2


def test_empty_idempotency_key_is_rejected(fake_database):
    headers = {**HEADERS, "X-Idempotency-Key": "   "}
    response = client.post("/api/v1/executions/", json=estimation_payload(), headers=headers)
    assert response.status_code == 422


# =========================================================
# PRUEBAS S2-150: FALLOS, TIMEOUTS Y PERSISTENCIA (MATHIAS)
# =========================================================

def test_execution_job_handles_internal_exception(fake_database):
    """Verifica que si el procesamiento falla, el estado persiste como FAILED (S2-150)."""
    payload = estimation_payload(scene_id="scene_fail")
    
    post_response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    job_id = post_response.json()["job_id"]
    
    db_record = next((row for row in fake_database.rows if row["id"] == job_id), None)
    
    assert db_record is not None
    assert db_record["status"] == "failed"
    assert db_record["error_message"] == "Excepción interna: Fallo al procesar los tensores de la escena."


def test_execution_job_handles_timeout_exceeded(monkeypatch, fake_database):
    """Verifica que el timeout aborte el trabajo y persista FAILED (S2-150)."""
    monkeypatch.setattr(execution_router, "JOB_TIMEOUT_SECONDS", 0.1)
    
    payload = estimation_payload(scene_id="scene_timeout")
    post_response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    job_id = post_response.json()["job_id"]
    
    db_record = next((row for row in fake_database.rows if row["id"] == job_id), None)
    
    assert db_record is not None
    assert db_record["status"] == "failed"
    assert "Timeout de 0.1s" in db_record["error_message"]


# =========================================================
# PRUEBAS S2-147: VALIDACION DE TRAINING (BARBARA)
# =========================================================

def test_training_requires_a_published_dataset_version(fake_database):
    fake_database.versions[0]["state"] = "APPROVED"
    response = client.post("/api/v1/executions/", json=training_payload(), headers=HEADERS)
    assert response.status_code == 409
    assert response.json()["message"] == "Solo se pueden entrenar versiones publicadas."
    assert fake_database.rows == []


def test_training_rejects_an_unknown_version(fake_database):
    payload = training_payload(version_id="dddddddd-dddd-4ddd-8ddd-dddddddddddd")
    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró la versión del dataset."
    assert fake_database.rows == []


def test_training_requires_a_version_id():
    payload = training_payload()
    payload["config"].pop("version_id")
    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_training_requires_dataset_id_to_be_a_uuid():
    payload = training_payload(dataset_id="id-invalido")
    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert response.status_code == 422


def test_training_requires_version_to_belong_to_dataset(fake_database):
    payload = training_payload(dataset_id="cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert response.json()["message"] == "La versión no pertenece al dataset indicado."
    assert fake_database.rows == []


def test_training_is_persisted_as_queued_and_returns_202(fake_database):
    response = client.post("/api/v1/executions/", json=training_payload(), headers=HEADERS)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["status_url"] == f"/api/v1/executions/{data['job_id']}"
    assert len(fake_database.rows) == 1
    
    # En FastAPI TestClient, las BackgroundTasks se ejecutan sincrónicamente
    # por lo que el objeto en base de datos ya transitó a "completed".
    assert fake_database.rows[0]["status"] == "completed"
    assert fake_database.rows[0]["job_type"] == "training"



