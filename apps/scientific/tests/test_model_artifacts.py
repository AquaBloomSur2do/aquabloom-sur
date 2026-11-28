import hashlib
from types import SimpleNamespace

import pytest
from postgrest.exceptions import APIError

from apps.scientific.app.domains.execution.model_artifacts import (
    ARTIFACT_URL_MAX_TTL_SECONDS,
    build_model_artifact_storage_path,
    calculate_sha256,
    create_model_artifact_signed_url,
    save_model_artifact,
)


class FakeStorageBucket:
    def __init__(self, remove_error=None, upload_error=None, sign_response=None):
        self.uploaded = []
        self.removed = []
        self.signed = []
        self.remove_error = remove_error
        self.upload_error = upload_error
        self.sign_response = sign_response

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

    def create_signed_url(self, path, expires_in):
        self.signed.append((path, expires_in))
        if self.sign_response is not None:
            return self.sign_response
        return {"signedURL": f"https://storage.test/sign/{path}?token=abc"}

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

SIGNED_JOB_ID = "11111111-1111-4111-8111-111111111111"
SIGNED_PATH = f"models/{SIGNED_JOB_ID}/model.pkl"


def _artifact_reference(**overrides):
    reference = {
        "job_id": SIGNED_JOB_ID,
        "bucket": "model_artifacts",
        "storage_path": SIGNED_PATH,
        "checksum": "a" * 64,
        "size_bytes": 12,
    }
    reference.update(overrides)
    return reference


def test_signed_url_is_created_in_private_bucket_with_expiry():
    client = FakeClient()

    url = create_model_artifact_signed_url(client, _artifact_reference(), 45)

    assert url == f"https://storage.test/sign/{SIGNED_PATH}?token=abc"
    assert client.storage.requested_bucket == "model_artifacts"
    assert client.storage.bucket.signed == [(SIGNED_PATH, 45)]


def test_signed_url_accepts_alternative_response_key():
    bucket = FakeStorageBucket(sign_response={"signedUrl": "https://storage.test/x"})
    client = FakeClient(bucket=bucket)

    url = create_model_artifact_signed_url(client, _artifact_reference())

    assert url == "https://storage.test/x"


@pytest.mark.parametrize(
    "storage_path",
    [
        "models/22222222-2222-4222-8222-222222222222/model.pkl",
        f"models/{SIGNED_JOB_ID}/../otro/model.pkl",
        "otra/ruta/model.pkl",
    ],
)
def test_signed_url_rejects_path_outside_the_job(storage_path):
    client = FakeClient()

    with pytest.raises(ValueError, match="no pertenece"):
        create_model_artifact_signed_url(
            client, _artifact_reference(storage_path=storage_path)
        )

    assert client.storage.bucket.signed == []


@pytest.mark.parametrize("overrides", [{"bucket": ""}, {"storage_path": None}])
def test_signed_url_rejects_incomplete_reference(overrides):
    client = FakeClient()

    with pytest.raises(ValueError, match="incompleta"):
        create_model_artifact_signed_url(client, _artifact_reference(**overrides))

    assert client.storage.bucket.signed == []


@pytest.mark.parametrize("expires_in", [0, -1, ARTIFACT_URL_MAX_TTL_SECONDS + 1])
def test_signed_url_rejects_out_of_range_expiry(expires_in):
    client = FakeClient()

    with pytest.raises(ValueError, match="rango"):
        create_model_artifact_signed_url(client, _artifact_reference(), expires_in)

    assert client.storage.bucket.signed == []


@pytest.mark.parametrize("expires_in", [True, "60", 1.5])
def test_signed_url_rejects_non_integer_expiry(expires_in):
    with pytest.raises(TypeError, match="entero"):
        create_model_artifact_signed_url(
            FakeClient(), _artifact_reference(), expires_in
        )


def test_signed_url_rejects_non_dict_reference():
    with pytest.raises(TypeError, match="referencia"):
        create_model_artifact_signed_url(FakeClient(), "no-es-un-dict")


def test_signed_url_fails_when_storage_returns_no_url():
    client = FakeClient(bucket=FakeStorageBucket(sign_response={}))

    with pytest.raises(ValueError, match="firmar"):
        create_model_artifact_signed_url(client, _artifact_reference())
        