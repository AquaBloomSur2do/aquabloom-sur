import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from apps.scientific.app.domains.execution.domain_execution import (
    JobLimitExceededError,
    execute_point_inference,
    verify_and_deserialize_model_artifact,
)
from apps.scientific.app.domains.execution.model_execution import (
    download_model_artifact_from_storage,
    get_registered_model_artifact_ref,
)
from apps.scientific.app.domains.execution.service_execution import (
    process_scientific_job,
)


class FakeStorageBucket:
    def __init__(self, artifact_bytes: bytes):
        self.artifact_bytes = artifact_bytes
        self.downloaded_paths: list[str] = []

    def download(self, storage_path: str) -> bytes:
        self.downloaded_paths.append(storage_path)
        return self.artifact_bytes


class FakeStorage:
    def __init__(self, bucket: FakeStorageBucket):
        self.bucket = bucket
        self.requested_bucket: str | None = None

    def from_(self, bucket: str) -> FakeStorageBucket:
        self.requested_bucket = bucket
        return self.bucket


class FakeQuery:
    def __init__(self, database: "FakeInferenceDatabase"):
        self.database = database
        self.payload: dict[str, object] | None = None

    def select(self, _columns: str) -> "FakeQuery":
        return self

    def eq(self, _column: str, _value: str) -> "FakeQuery":
        return self

    def limit(self, _limit: int) -> "FakeQuery":
        return self

    def update(self, payload: dict[str, object]) -> "FakeQuery":
        self.payload = payload
        return self

    def execute(self) -> SimpleNamespace:
        if self.payload is not None:
            self.database.row.update(self.payload)
        return SimpleNamespace(
            data=[{"result": self.database.row.get("result")}]
        )


class FakeInferenceDatabase:
    def __init__(
        self,
        artifact_bytes: bytes,
        *,
        include_reference: bool = True,
    ):
        checksum = hashlib.sha256(artifact_bytes).hexdigest()
        result = (
            {
                "model_artifact": {
                    "bucket": "model_artifacts",
                    "storage_path": "models/job-123/model.json",
                    "checksum": checksum,
                }
            }
            if include_reference
            else {}
        )
        self.row = {
            "id": "job-123",
            "status": "queued",
            "result": result,
        }
        self.storage = FakeStorage(FakeStorageBucket(artifact_bytes))

    def table(self, table_name: str) -> FakeQuery:
        assert table_name == "scientific_jobs"
        return FakeQuery(self)


def test_verify_and_deserialize_model_artifact_checksum_valid_and_corrupt():
    artifact_bytes = json.dumps({"prediction_value": 12.5}).encode()
    checksum = hashlib.sha256(artifact_bytes).hexdigest()

    artifact = verify_and_deserialize_model_artifact(artifact_bytes, checksum)

    assert artifact["prediction_value"] == 12.5
    with pytest.raises(ValueError, match="Checksum"):
        verify_and_deserialize_model_artifact(artifact_bytes, "0" * 64)
    with pytest.raises(ValueError, match="JSON inválido"):
        verify_and_deserialize_model_artifact(
            b"{invalid", hashlib.sha256(b"{invalid").hexdigest()
        )


def test_execute_point_inference_supports_baseline_and_linear_artifacts():
    points = [
        {"point_id": "p1", "latitude": -38.0, "longitude": -72.0, "features": {"ndci": 0.2}},
        {"point_id": "p2", "latitude": -39.0, "longitude": -73.0, "features": {"ndci": 0.5}},
    ]

    baseline = execute_point_inference({"prediction_value": 12.5}, points)
    linear = execute_point_inference(
        {"intercept": 5.0, "coefficients": {"ndci": 10.0}},
        points,
    )

    assert [row["predicted_value"] for row in baseline] == [12.5, 12.5]
    assert [row["predicted_value"] for row in linear] == [7.0, 10.0]


def test_execute_point_inference_rejects_empty_over_limit_and_missing_model():
    with pytest.raises(ValueError, match="vacía"):
        execute_point_inference({"prediction_value": 12.5}, [])

    too_many_points = [
        {"point_id": str(index), "features": {}}
        for index in range(101)
    ]
    with pytest.raises(JobLimitExceededError, match="máximo 100"):
        execute_point_inference(
            {"prediction_value": 12.5},
            too_many_points,
        )


def test_registered_reference_and_storage_download():
    artifact_bytes = json.dumps({"prediction_value": 12.5}).encode()
    database = FakeInferenceDatabase(artifact_bytes)

    reference = get_registered_model_artifact_ref(database, "job-123")
    downloaded = download_model_artifact_from_storage(
        database,
        reference["bucket"],
        reference["storage_path"],
    )

    assert reference["bucket"] == "model_artifacts"
    assert reference["storage_path"] == "models/job-123/model.json"
    assert reference["checksum"] == hashlib.sha256(artifact_bytes).hexdigest()
    assert downloaded == artifact_bytes
    assert database.storage.requested_bucket == "model_artifacts"
    assert database.storage.bucket.downloaded_paths == [
        "models/job-123/model.json"
    ]


def test_process_estimation_persists_completed_predictions(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    artifact_bytes = json.dumps(
        {"intercept": 2.0, "coefficients": {"ndci": 20.0}}
    ).encode()
    database = FakeInferenceDatabase(artifact_bytes)
    monkeypatch.setattr(service_execution, "supabase", database)
    config = {
        "model_id": "job-123",
        "scene_id": "scene-123",
        "points": [
            {"point_id": "p1", "latitude": -38.0, "longitude": -72.0, "features": {"ndci": 0.2}},
            {"point_id": "p2", "latitude": -39.0, "longitude": -73.0, "features": {"ndci": 0.5}},
        ],
    }

    asyncio.run(
        process_scientific_job(
            "job-123",
            "estimation",
            config,
        )
    )

    assert database.row["status"] == "completed"
    assert database.row["result"]["model_id"] == "job-123"
    assert database.row["result"]["point_count"] == 2
    assert [
        item["predicted_value"]
        for item in database.row["result"]["predictions"]
    ] == [6.0, 12.0]
    assert database.storage.requested_bucket == "model_artifacts"


def test_process_estimation_persists_failed_when_artifact_missing(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    database = FakeInferenceDatabase(
        json.dumps({"prediction_value": 12.5}).encode(),
        include_reference=False,
    )
    monkeypatch.setattr(service_execution, "supabase", database)
    config = {
        "model_id": "job-123",
        "scene_id": "scene-123",
        "points": [{"point_id": "p1", "features": {}}],
    }

    asyncio.run(
        process_scientific_job(
            "job-123",
            "estimation",
            config,
        )
    )

    assert database.row["status"] == "failed"
    assert database.row["result"] is None
    assert "artefacto" in database.row["error_message"].lower()


def test_process_estimation_persists_failed_when_checksum_is_invalid(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    database = FakeInferenceDatabase(
        json.dumps({"prediction_value": 12.5}).encode()
    )
    database.row["result"]["model_artifact"]["checksum"] = "0" * 64
    monkeypatch.setattr(service_execution, "supabase", database)
    config = {
        "model_id": "job-123",
        "scene_id": "scene-123",
        "points": [{"point_id": "p1", "features": {}}],
    }

    asyncio.run(
        process_scientific_job(
            "job-123",
            "estimation",
            config,
        )
    )

    assert database.row["status"] == "failed"
    assert database.row["result"] is None
    assert "checksum" in database.row["error_message"].lower()
