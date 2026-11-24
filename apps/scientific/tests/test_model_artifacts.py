import hashlib
from types import SimpleNamespace

import pytest
from postgrest.exceptions import APIError

from apps.scientific.app.domains.execution.model_artifacts import (
    build_model_artifact_storage_path,
    calculate_sha256,
    save_model_artifact,
)


class FakeStorageBucket:
    def __init__(self):
        self.uploaded = []
        self.removed = []

    def upload(self, path, data, file_options):
        self.uploaded.append((path, data, file_options))
        return {"path": path}

    def remove(self, paths):
        self.removed.extend(paths)
        return {"removed": paths}


class FakeStorage:
    def __init__(self, bucket):
        self.bucket = bucket
        self.requested_bucket = None

    def from_(self, bucket):
        self.requested_bucket = bucket
        return self.bucket


class FakeQuery:
    def __init__(self, database, payload=None):
        self.database = database
        self.payload = payload

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def limit(self, _limit):
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.payload is not None:
            if self.database.update_error is not None:
                raise self.database.update_error
            self.database.update_payload = self.payload
        return SimpleNamespace(data=[{"result": self.database.previous_result}])


class FakeClient:
    def __init__(self, bucket=None, previous_result=None, update_error=None):
        self.storage = FakeStorage(bucket or FakeStorageBucket())
        self.previous_result = previous_result
        self.update_error = update_error
        self.update_payload = None

    def table(self, table_name):
        assert table_name == "scientific_jobs"
        return FakeQuery(self)


def test_calculate_sha256_is_deterministic():
    artifact = b"\x00model-data\xff"

    first = calculate_sha256(artifact)
    second = calculate_sha256(artifact)

    assert first == second
    assert first == hashlib.sha256(artifact).hexdigest()
    assert len(first) == 64


def test_build_model_artifact_storage_path():
    assert (
        build_model_artifact_storage_path("job-123", "../model.bin")
        == "models/job-123/model.bin"
    )


def test_save_model_artifact_uploads_and_updates_job_result():
    bucket = FakeStorageBucket()
    client = FakeClient(
        bucket=bucket,
        previous_result={"accuracy": 0.98, "processed_pixels": 102400},
    )

    reference = save_model_artifact(
        client,
        "job-123",
        b"model-content",
        filename="model.bin",
    )

    assert client.storage.requested_bucket == "model_artifacts"
    assert bucket.uploaded == [
        (
            "models/job-123/model.bin",
            b"model-content",
            {"content-type": "application/octet-stream"},
        )
    ]
    assert client.update_payload["result"]["accuracy"] == 0.98
    assert client.update_payload["result"]["processed_pixels"] == 102400
    assert client.update_payload["result"]["model_artifact"] == {
        "job_id": "job-123",
        "bucket": "model_artifacts",
        "storage_path": "models/job-123/model.bin",
        "checksum": hashlib.sha256(b"model-content").hexdigest(),
        "size_bytes": len(b"model-content"),
    }
    assert reference.job_id == "job-123"
    assert reference.bucket == "model_artifacts"
    assert reference.storage_path == "models/job-123/model.bin"
    assert reference.checksum == hashlib.sha256(b"model-content").hexdigest()
    assert reference.size_bytes == len(b"model-content")


def test_save_model_artifact_removes_upload_when_database_update_fails():
    bucket = FakeStorageBucket()
    error = APIError({"message": "database update failed", "code": "23514"})
    client = FakeClient(
        bucket=bucket,
        update_error=error,
    )

    with pytest.raises(APIError):
        save_model_artifact(client, "job-123", b"model-content")

    assert bucket.uploaded[0][0] == "models/job-123/model.pkl"
    assert bucket.removed == ["models/job-123/model.pkl"]
