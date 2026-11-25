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
    def __init__(self, remove_error=None, upload_error=None):
        self.uploaded = []
        self.removed = []
        self.remove_error = remove_error
        self.upload_error = upload_error

    def upload(self, path, data, file_options):
        self.uploaded.append((path, data, file_options))
        if self.upload_error is not None:
            raise self.upload_error
        return {"path": path}

    def remove(self, paths):
        if self.remove_error is not None:
            raise self.remove_error
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
        self.filters = []

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
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
            if self.database.job_exists and not self.database.update_returns_no_rows:
                return SimpleNamespace(
                    data=[
                        {"id": self.database.job_id, "result": self.payload["result"]}
                    ]
                )
            return SimpleNamespace(data=[])
        if self.database.job_exists:
            return SimpleNamespace(
                data=[
                    {
                        "id": self.database.job_id,
                        "result": self.database.previous_result,
                    }
                ]
            )
        return SimpleNamespace(data=[])


class FakeClient:
    def __init__(
        self,
        bucket=None,
        previous_result=None,
        update_error=None,
        job_exists=True,
        update_returns_no_rows=False,
    ):
        self.storage = FakeStorage(bucket or FakeStorageBucket())
        self.previous_result = previous_result
        self.update_error = update_error
        self.update_payload = None
        self.job_exists = job_exists
        self.update_returns_no_rows = update_returns_no_rows
        self.job_id = "11111111-1111-4111-8111-111111111111"
        self.queries = []

    def table(self, table_name):
        assert table_name == "scientific_jobs"
        query = FakeQuery(self)
        self.queries.append(query)
        return query


def test_calculate_sha256_is_deterministic():
    artifact = b"\x00model-data\xff"

    first = calculate_sha256(artifact)
    second = calculate_sha256(artifact)

    assert first == second
    assert first == hashlib.sha256(artifact).hexdigest()
    assert len(first) == 64


def test_build_model_artifact_storage_path():
    job_id = "11111111-1111-4111-8111-111111111111"
    assert build_model_artifact_storage_path(job_id, "model.bin") == (
        f"models/{job_id}/model.bin"
    )


@pytest.mark.parametrize(
    "job_id",
    ["job-123", "../otro", "/tmp/otro", "11111111-1111-4111-8111-111111111111/extra"],
)
def test_build_model_artifact_storage_path_rejects_invalid_job_id(job_id):
    with pytest.raises(ValueError, match="UUID"):
        build_model_artifact_storage_path(job_id, "model.bin")


@pytest.mark.parametrize(
    "filename", ["", ".", "..", "../model.bin", "folder/model.bin", "folder\\model.bin"]
)
def test_build_model_artifact_storage_path_rejects_invalid_filename(filename):
    job_id = "11111111-1111-4111-8111-111111111111"
    with pytest.raises(ValueError, match="filename"):
        build_model_artifact_storage_path(job_id, filename)


def test_save_model_artifact_uploads_and_updates_job_result():
    bucket = FakeStorageBucket()
    client = FakeClient(
        bucket=bucket,
        previous_result={"accuracy": 0.98, "processed_pixels": 102400},
    )
    job_id = "11111111-1111-4111-8111-111111111111"

    reference = save_model_artifact(
        client,
        job_id,
        b"model-content",
        filename="model.bin",
    )

    assert client.storage.requested_bucket == "model_artifacts"
    assert bucket.uploaded == [
        (
            f"models/{job_id}/model.bin",
            b"model-content",
            {"content-type": "application/octet-stream"},
        )
    ]
    assert client.update_payload["result"]["accuracy"] == 0.98
    assert client.update_payload["result"]["processed_pixels"] == 102400
    assert client.update_payload["result"]["model_artifact"] == {
        "job_id": job_id,
        "bucket": "model_artifacts",
        "storage_path": f"models/{job_id}/model.bin",
        "checksum": hashlib.sha256(b"model-content").hexdigest(),
        "size_bytes": len(b"model-content"),
    }
    assert reference.job_id == job_id
    assert reference.bucket == "model_artifacts"
    assert reference.storage_path == f"models/{job_id}/model.bin"
    assert reference.checksum == hashlib.sha256(b"model-content").hexdigest()
    assert reference.size_bytes == len(b"model-content")
    assert all(("id", job_id) in query.filters for query in client.queries)


def test_save_model_artifact_removes_upload_when_database_update_fails():
    bucket = FakeStorageBucket()
    error = APIError({"message": "database update failed", "code": "23514"})
    client = FakeClient(
        bucket=bucket,
        update_error=error,
    )
    job_id = "11111111-1111-4111-8111-111111111111"

    with pytest.raises(APIError):
        save_model_artifact(client, job_id, b"model-content")

    assert bucket.uploaded[0][0] == f"models/{job_id}/model.pkl"
    assert bucket.removed == [f"models/{job_id}/model.pkl"]


def test_save_model_artifact_does_not_remove_when_upload_fails():
    upload_error = RuntimeError("storage upload failed")
    bucket = FakeStorageBucket(upload_error=upload_error)
    client = FakeClient(bucket=bucket)
    job_id = "11111111-1111-4111-8111-111111111111"

    with pytest.raises(RuntimeError) as exc_info:
        save_model_artifact(client, job_id, b"model-content")

    assert exc_info.value is upload_error
    assert bucket.removed == []


def test_save_model_artifact_removes_upload_when_update_returns_no_rows():
    bucket = FakeStorageBucket()
    client = FakeClient(bucket=bucket, update_returns_no_rows=True)
    job_id = "11111111-1111-4111-8111-111111111111"
    expected_storage_path = f"models/{job_id}/model.pkl"

    with pytest.raises(ValueError, match="no pudo actualizarse"):
        save_model_artifact(client, job_id, b"model-content")

    assert bucket.removed == [expected_storage_path]


def test_save_model_artifact_preserves_database_error_when_remove_fails(caplog):
    remove_error = RuntimeError("storage cleanup failed")
    bucket = FakeStorageBucket(remove_error=remove_error)
    database_error = APIError({"message": "database update failed", "code": "23514"})
    client = FakeClient(bucket=bucket, update_error=database_error)
    job_id = "11111111-1111-4111-8111-111111111111"

    with pytest.raises(APIError) as exc_info:
        save_model_artifact(client, job_id, b"model-content")

    assert exc_info.value is database_error
    assert "No se pudo limpiar el artefacto" in caplog.text
    assert "storage cleanup failed" in caplog.text


def test_save_model_artifact_rejects_missing_job_before_upload():
    bucket = FakeStorageBucket()
    client = FakeClient(bucket=bucket, job_exists=False)
    job_id = "11111111-1111-4111-8111-111111111111"

    with pytest.raises(ValueError, match="no existe"):
        save_model_artifact(client, job_id, b"model-content")

    assert bucket.uploaded == []
    assert bucket.removed == []


def test_save_model_artifact_rejects_empty_artifact():
    job_id = "11111111-1111-4111-8111-111111111111"
    client = FakeClient()

    with pytest.raises(ValueError, match="vacío"):
        save_model_artifact(client, job_id, b"")


def test_save_model_artifact_normalizes_bucket():
    bucket = FakeStorageBucket()
    client = FakeClient(bucket=bucket)
    job_id = "11111111-1111-4111-8111-111111111111"

    reference = save_model_artifact(
        client,
        job_id,
        b"model-content",
        bucket="  model_artifacts  ",
    )

    assert client.storage.requested_bucket == "model_artifacts"
    assert reference.bucket == "model_artifacts"


@pytest.mark.parametrize("job_id", ["job-123", "../otro", "/tmp/otro"])
def test_save_model_artifact_rejects_invalid_job_id(job_id):
    client = FakeClient()

    with pytest.raises(ValueError, match="UUID"):
        save_model_artifact(client, job_id, b"model-content")


@pytest.mark.parametrize("bucket", ["", "   ", None])
def test_save_model_artifact_rejects_invalid_bucket(bucket):
    job_id = "11111111-1111-4111-8111-111111111111"
    client = FakeClient()

    with pytest.raises((TypeError, ValueError)):
        save_model_artifact(client, job_id, b"model-content", bucket=bucket)
