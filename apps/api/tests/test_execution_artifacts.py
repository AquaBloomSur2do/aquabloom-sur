import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import settings
from app.main import app
from domain.execution import artifacts

settings.internal_service_token = SecretStr("test-secret-token")
client = TestClient(app)
HEADERS = {"X-Internal-Token": "test-secret-token"}
TRAINING_JOB_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
FILE_CONTENT = b"model weights"


class FakeQuery:
    def __init__(self, database, table):
        self.database = database
        self.table_name = table
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
        if self.table_name == "scientific_jobs":
            rows = [
                job
                for job in self.database.jobs
                if all(
                    str(job.get(key)) == str(value)
                    for key, value in self.filters.items()
                )
            ]
            return SimpleNamespace(data=rows)

        if self.table_name == "model_artifacts":
            if self.insert_data is not None:
                if self.database.fail_artifact_insert:
                    raise RuntimeError("Simulated database error")
                row = {
                    **self.insert_data,
                    "id": str(uuid4()),
                    "created_at": datetime.now(UTC).isoformat(),
                }
                self.database.artifacts.append(row)
                return SimpleNamespace(data=[row])
            rows = [
                artifact
                for artifact in self.database.artifacts
                if all(
                    str(artifact.get(key)) == str(value)
                    for key, value in self.filters.items()
                )
            ]
            return SimpleNamespace(data=rows)

        raise AssertionError(f"Unexpected table: {self.table_name}")


class FakeBucket:
    def __init__(self, database):
        self.database = database

    def upload(self, path, content, file_options):
        self.database.storage_objects[path] = bytes(content)
        self.database.upload_options[path] = file_options

    def remove(self, paths):
        for path in paths:
            self.database.storage_objects.pop(path, None)


class FakeStorage:
    def __init__(self, database):
        self.database = database

    def from_(self, _bucket):
        return FakeBucket(self.database)


class FakeDatabase:
    def __init__(self):
        self.jobs = [
            {"id": TRAINING_JOB_ID, "job_type": "training"},
            {"id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "job_type": "estimation"},
        ]
        self.artifacts = []
        self.storage_objects = {}
        self.upload_options = {}
        self.fail_artifact_insert = False
        self.storage = FakeStorage(self)

    def table(self, table_name):
        return FakeQuery(self, table_name)


@pytest.fixture
def fake_database(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(artifacts, "supabase", database)
    return database


def test_upload_persists_artifact_and_sha256_reference(fake_database):
    response = client.post(
        f"/api/v1/executions/{TRAINING_JOB_ID}/artifact",
        headers=HEADERS,
        files={"file": ("weights.bin", FILE_CONTENT, "application/octet-stream")},
    )

    assert response.status_code == 201
    body = response.json()
    checksum = hashlib.sha256(FILE_CONTENT).hexdigest()
    assert body["training_job_id"] == TRAINING_JOB_ID
    assert body["filename"] == "weights.bin"
    assert body["file_size"] == len(FILE_CONTENT)
    assert body["checksum"] == checksum
    assert body["storage_path"] == f"{TRAINING_JOB_ID}/{checksum}"
    assert fake_database.storage_objects[body["storage_path"]] == FILE_CONTENT
    assert fake_database.artifacts[0]["training_job_id"] == TRAINING_JOB_ID
    assert fake_database.artifacts[0]["checksum"] == checksum
    assert fake_database.upload_options[body["storage_path"]]["upsert"] == "false"


def test_upload_rejects_non_training_job(fake_database):
    response = client.post(
        "/api/v1/executions/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb/artifact",
        headers=HEADERS,
        files={"file": ("weights.bin", FILE_CONTENT, "application/octet-stream")},
    )

    assert response.status_code == 409
    assert fake_database.storage_objects == {}


def test_upload_rejects_unknown_training_job(fake_database):
    response = client.post(
        "/api/v1/executions/cccccccc-cccc-4ccc-8ccc-cccccccccccc/artifact",
        headers=HEADERS,
        files={"file": ("weights.bin", FILE_CONTENT, "application/octet-stream")},
    )

    assert response.status_code == 404
    assert fake_database.storage_objects == {}


def test_upload_rejects_empty_artifact(fake_database):
    response = client.post(
        f"/api/v1/executions/{TRAINING_JOB_ID}/artifact",
        headers=HEADERS,
        files={"file": ("weights.bin", b"", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert fake_database.storage_objects == {}


def test_upload_rejects_artifact_larger_than_limit(fake_database, monkeypatch):
    monkeypatch.setattr(artifacts, "MAX_MODEL_ARTIFACT_SIZE", 4)

    response = client.post(
        f"/api/v1/executions/{TRAINING_JOB_ID}/artifact",
        headers=HEADERS,
        files={"file": ("weights.bin", b"12345", "application/octet-stream")},
    )

    assert response.status_code == 413
    assert fake_database.storage_objects == {}


def test_upload_is_idempotent_for_same_checksum_and_rejects_replacement(
    fake_database,
):
    path = f"/api/v1/executions/{TRAINING_JOB_ID}/artifact"

    def upload(content):
        return client.post(
            path,
            headers=HEADERS,
            files={"file": ("weights.bin", content, "application/octet-stream")},
        )

    first = upload(FILE_CONTENT)
    repeated = upload(FILE_CONTENT)
    replacement = upload(b"different weights")

    assert first.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json()["checksum"] == first.json()["checksum"]
    assert replacement.status_code == 409
    assert len(fake_database.artifacts) == 1


def test_get_model_artifact_returns_saved_metadata(fake_database):
    uploaded = client.post(
        f"/api/v1/executions/{TRAINING_JOB_ID}/artifact",
        headers=HEADERS,
        files={"file": ("weights.bin", FILE_CONTENT, "application/octet-stream")},
    )

    response = client.get(
        f"/api/v1/executions/{TRAINING_JOB_ID}/artifact",
        headers=HEADERS,
    )

    assert uploaded.status_code == 201
    assert response.status_code == 200
    assert response.json() == uploaded.json()


def test_upload_removes_storage_object_if_database_insert_fails(fake_database):
    fake_database.fail_artifact_insert = True

    response = client.post(
        f"/api/v1/executions/{TRAINING_JOB_ID}/artifact",
        headers=HEADERS,
        files={"file": ("weights.bin", FILE_CONTENT, "application/octet-stream")},
    )

    assert response.status_code == 502
    assert fake_database.storage_objects == {}


def test_upload_requires_internal_authentication(fake_database):
    response = client.post(
        f"/api/v1/executions/{TRAINING_JOB_ID}/artifact",
        files={"file": ("weights.bin", FILE_CONTENT, "application/octet-stream")},
    )

    assert response.status_code == 401
    assert fake_database.storage_objects == {}
