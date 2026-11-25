import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from storage3.utils import StorageException

from apps.scientific.app.domains.execution.domain_execution import (
    JobLimitExceededError,
    execute_point_inference,
    verify_and_deserialize_model_artifact,
)
from apps.scientific.app.domains.execution.model_execution import (
    download_model_artifact_from_storage,
    get_registered_model_artifact_ref,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    EstimationConfig,
    InferencePoint,
)
from apps.scientific.app.domains.execution.service_execution import (
    process_scientific_job,
)

ORGANIZATION_ID = "org-123"
MODEL_ID = "11111111-1111-4111-8111-111111111111"
JOB_ID = "job-123"


class FakeStorageBucket:
    def __init__(
        self,
        artifact_bytes: bytes,
        download_error: Exception | None = None,
    ):
        self.artifact_bytes = artifact_bytes
        self.download_error = download_error
        self.downloaded_paths: list[str] = []

    def download(self, storage_path: str) -> bytes:
        self.downloaded_paths.append(storage_path)
        if self.download_error is not None:
            raise self.download_error
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
        self.filters: list[tuple[str, str]] = []
        self.selected_columns: str | None = None
        self.limit_value: int | None = None

    def select(self, columns: str) -> "FakeQuery":
        self.selected_columns = columns
        return self

    def eq(self, column: str, value: str) -> "FakeQuery":
        self.filters.append((column, value))
        return self

    def limit(self, limit: int) -> "FakeQuery":
        self.limit_value = limit
        return self

    def update(self, payload: dict[str, object]) -> "FakeQuery":
        self.payload = payload
        return self

    def execute(self) -> SimpleNamespace:
        matched_rows = [
            row
            for row in self.database.rows
            if all(row.get(column) == value for column, value in self.filters)
        ]
        if self.limit_value is not None:
            matched_rows = matched_rows[: self.limit_value]

        if self.payload is not None:
            for row in matched_rows:
                row.update(self.payload)
        return SimpleNamespace(
            data=[
                {"id": row.get("id"), "result": row.get("result")}
                for row in matched_rows
            ]
        )


class FakeInferenceDatabase:
    def __init__(
        self,
        artifact_bytes: bytes,
        *,
        include_reference: bool = True,
        additional_rows: list[dict[str, object]] | None = None,
        download_error: Exception | None = None,
    ):
        checksum = hashlib.sha256(artifact_bytes).hexdigest()
        result = (
            {
                "model_artifact": {
                    "bucket": " model_artifacts ",
                    "storage_path": " models/model-123/model.json ",
                    "checksum": checksum,
                }
            }
            if include_reference
            else {}
        )
        self.training_row: dict[str, object] = {
            "id": MODEL_ID,
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "completed",
            "result": result,
        }
        self.estimation_row: dict[str, object] = {
            "id": JOB_ID,
            "organization_id": ORGANIZATION_ID,
            "job_type": "estimation",
            "status": "queued",
            "result": None,
        }
        self.rows = [
            self.training_row,
            self.estimation_row,
            *(additional_rows or []),
        ]
        self.storage = FakeStorage(
            FakeStorageBucket(artifact_bytes, download_error=download_error)
        )
        self.queries: list[FakeQuery] = []

    def table(self, table_name: str) -> FakeQuery:
        assert table_name == "scientific_jobs"
        query = FakeQuery(self)
        self.queries.append(query)
        return query


def test_verify_and_deserialize_model_artifact_checksum_valid_and_corrupt():
    artifact_bytes = json.dumps({"prediction_value": 12.5}).encode()
    checksum = hashlib.sha256(artifact_bytes).hexdigest()

    artifact = verify_and_deserialize_model_artifact(artifact_bytes, checksum)

    assert artifact["prediction_value"] == 12.5
    assert (
        verify_and_deserialize_model_artifact(artifact_bytes, checksum.upper())
        == artifact
    )
    with pytest.raises(ValueError, match="Checksum"):
        verify_and_deserialize_model_artifact(artifact_bytes, "0" * 64)
    with pytest.raises(ValueError, match="checksum"):
        verify_and_deserialize_model_artifact(artifact_bytes, "g" * 64)
    with pytest.raises(ValueError, match="JSON inválido"):
        verify_and_deserialize_model_artifact(
            b"{invalid", hashlib.sha256(b"{invalid").hexdigest()
        )


def test_execute_point_inference_supports_baseline_and_linear_artifacts():
    points = [
        {
            "point_id": " p1 ",
            "latitude": -38.0,
            "longitude": -72.0,
            "features": {"ndci": 0.2},
        },
        {
            "point_id": "p2",
            "latitude": -39.0,
            "longitude": -73.0,
            "features": {"ndci": 0.5},
        },
    ]

    baseline = execute_point_inference({"prediction_value": 12.5}, points)
    linear = execute_point_inference(
        {"intercept": 5.0, "coefficients": {"ndci": 10.0}},
        points,
    )

    assert [row["predicted_value"] for row in baseline] == [12.5, 12.5]
    assert [row["predicted_value"] for row in linear] == [7.0, 10.0]
    assert baseline[0]["point_id"] == "p1"


def test_execute_point_inference_supports_single_coefficient():
    predictions = execute_point_inference(
        {"intercept": 2.0, "coefficient": 10.0},
        [{"point_id": "p1", "features": {"ndci": 0.5}}],
    )

    assert predictions[0]["predicted_value"] == 7.0


def test_execute_point_inference_rejects_empty_over_limit_and_missing_model():
    with pytest.raises(ValueError, match="vacía"):
        execute_point_inference({"prediction_value": 12.5}, [])

    too_many_points = [{"point_id": str(index), "features": {}} for index in range(101)]
    with pytest.raises(JobLimitExceededError, match="máximo 100"):
        execute_point_inference({"prediction_value": 12.5}, too_many_points)

    valid_point = [{"point_id": "p1", "features": {}}]
    with pytest.raises(TypeError, match="intercept"):
        execute_point_inference({}, valid_point)
    with pytest.raises(ValueError, match="coefficients"):
        execute_point_inference(
            {"intercept": 1.0, "coefficients": {}},
            valid_point,
        )


@pytest.mark.parametrize(
    ("features", "error", "message"),
    [
        ({}, TypeError, "feature 'ndci'"),
        ({"ndci": float("nan")}, ValueError, "no es finito"),
        ({"ndci": float("inf")}, ValueError, "no es finito"),
    ],
)
def test_execute_point_inference_rejects_missing_or_nonfinite_features(
    features, error, message
):
    with pytest.raises(error, match=message):
        execute_point_inference(
            {"intercept": 1.0, "coefficients": {"ndci": 2.0}},
            [{"point_id": "p1", "features": features}],
        )


@pytest.mark.parametrize(
    ("coordinate", "value", "expected_error"),
    [
        ("latitude", 91.0, ValueError),
        ("longitude", -181.0, ValueError),
        ("latitude", True, TypeError),
        ("longitude", float("inf"), ValueError),
    ],
)
def test_execute_point_inference_rejects_invalid_coordinates(
    coordinate, value, expected_error
):
    point = {"point_id": "p1", coordinate: value, "features": {}}

    with pytest.raises(expected_error, match=coordinate):
        execute_point_inference({"prediction_value": 1.0}, [point])


@pytest.mark.parametrize(
    "point",
    [
        {"point_id": ""},
        {"point_id": "   "},
        {"point_id": "p1", "latitude": 91},
        {"point_id": "p1", "longitude": -181},
        {"point_id": "p1", "features": {"ndci": float("nan")}},
        {"point_id": "p1", "features": {"ndci": float("inf")}},
    ],
)
def test_inference_point_rejects_invalid_values(point):
    with pytest.raises(ValidationError):
        InferencePoint.model_validate(point)


def test_inference_point_normalizes_point_id():
    point = InferencePoint.model_validate({"point_id": " p1 "})

    assert point.point_id == "p1"


@pytest.mark.parametrize(
    "config",
    [
        {"model_id": "", "scene_id": "scene-1"},
        {"model_id": "   ", "scene_id": "scene-1"},
        {"model_id": "model-1", "scene_id": ""},
        {"model_id": "model-1", "scene_id": "   "},
        {"model_id": "model-1", "scene_id": "scene-1", "points": []},
    ],
)
def test_estimation_config_rejects_empty_ids_and_points(config):
    with pytest.raises(ValidationError):
        EstimationConfig.model_validate(config)


def test_estimation_config_normalizes_ids_and_keeps_legacy_points_none():
    config = EstimationConfig.model_validate(
        {"model_id": " model-1 ", "scene_id": " scene-1 "}
    )

    assert config.model_id == "model-1"
    assert config.scene_id == "scene-1"
    assert config.points is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("organization_id", "org-other"),
        ("job_type", "estimation"),
        ("status", "queued"),
    ],
)
def test_registered_reference_rejects_wrong_organization_or_job(field, value):
    artifact_bytes = json.dumps({"prediction_value": 12.5}).encode()
    other_org_row = {
        "id": MODEL_ID,
        "organization_id": "org-other",
        "job_type": "training",
        "status": "completed",
        "result": {"model_artifact": {}},
    }
    database = FakeInferenceDatabase(artifact_bytes, additional_rows=[other_org_row])
    database.training_row[field] = value

    with pytest.raises(ValueError, match="no encontrado"):
        get_registered_model_artifact_ref(database, MODEL_ID, ORGANIZATION_ID)

    assert database.queries[-1].filters == [
        ("id", MODEL_ID),
        ("organization_id", ORGANIZATION_ID),
        ("job_type", "training"),
        ("status", "completed"),
    ]
    assert database.queries[-1].limit_value == 1


def test_registered_reference_and_storage_download_normalize_paths():
    artifact_bytes = json.dumps({"prediction_value": 12.5}).encode()
    database = FakeInferenceDatabase(artifact_bytes)

    reference = get_registered_model_artifact_ref(
        database, f" {MODEL_ID} ", f" {ORGANIZATION_ID} "
    )
    downloaded = download_model_artifact_from_storage(
        database,
        f" {reference['bucket']} ",
        f" {reference['storage_path']} ",
    )

    assert reference["bucket"] == "model_artifacts"
    assert reference["storage_path"] == "models/model-123/model.json"
    assert reference["checksum"] == hashlib.sha256(artifact_bytes).hexdigest()
    assert downloaded == artifact_bytes
    assert database.storage.requested_bucket == "model_artifacts"
    assert database.storage.bucket.downloaded_paths == ["models/model-123/model.json"]


def test_download_model_artifact_wraps_storage_exception():
    storage_error = StorageException("storage unavailable")
    database = FakeInferenceDatabase(
        b"artifact",
        download_error=storage_error,
    )

    with pytest.raises(ValueError, match="no encontrado") as exc_info:
        download_model_artifact_from_storage(
            database, "model_artifacts", "models/model.json"
        )

    assert exc_info.value.__cause__ is storage_error


def test_process_estimation_persists_completed_predictions(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    artifact_bytes = json.dumps(
        {"intercept": 2.0, "coefficients": {"ndci": 20.0}}
    ).encode()
    database = FakeInferenceDatabase(artifact_bytes)
    monkeypatch.setattr(service_execution, "supabase", database)
    config = {
        "model_id": MODEL_ID,
        "scene_id": "scene-123",
        "points": [
            {
                "point_id": "p1",
                "latitude": -38.0,
                "longitude": -72.0,
                "features": {"ndci": 0.2},
            },
            {
                "point_id": "p2",
                "latitude": -39.0,
                "longitude": -73.0,
                "features": {"ndci": 0.5},
            },
        ],
    }

    asyncio.run(
        process_scientific_job(
            JOB_ID,
            "estimation",
            config,
            organization_id=ORGANIZATION_ID,
        )
    )

    result = database.estimation_row["result"]
    assert database.estimation_row["status"] == "completed"
    assert result["model_id"] == MODEL_ID
    assert result["scene_id"] == "scene-123"
    assert result["model_type"] == "linear"
    assert result["point_count"] == 2
    assert [item["predicted_value"] for item in result["predictions"]] == [6.0, 12.0]
    assert database.estimation_row["model_version_id"] == MODEL_ID
    assert database.storage.requested_bucket == "model_artifacts"


def test_process_estimation_legacy_without_points_remains_supported(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    database = FakeInferenceDatabase(b"unused")
    monkeypatch.setattr(service_execution, "supabase", database)

    asyncio.run(
        process_scientific_job(
            JOB_ID,
            "estimation",
            {"model_id": MODEL_ID, "scene_id": "scene-123", "points": None},
            organization_id=ORGANIZATION_ID,
        )
    )

    assert database.estimation_row["status"] == "completed"
    assert "no implementado" in database.estimation_row["result"]["message"]
    assert database.storage.bucket.downloaded_paths == []


def test_process_estimation_exceeds_point_limit_before_storage_download(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    database = FakeInferenceDatabase(b"unused")
    monkeypatch.setattr(service_execution, "supabase", database)
    config = {
        "model_id": MODEL_ID,
        "scene_id": "scene-123",
        "points": [{"point_id": str(index), "features": {}} for index in range(101)],
    }

    asyncio.run(
        process_scientific_job(
            JOB_ID,
            "estimation",
            config,
            organization_id=ORGANIZATION_ID,
        )
    )

    assert database.estimation_row["status"] == "failed"
    assert "máximo 100" in database.estimation_row["error_message"]
    assert database.storage.bucket.downloaded_paths == []


@pytest.mark.parametrize(
    ("training_updates", "organization_id"),
    [
        ({"organization_id": "org-other"}, ORGANIZATION_ID),
        ({"job_type": "estimation"}, ORGANIZATION_ID),
        ({"status": "queued"}, ORGANIZATION_ID),
        ({}, "org-other"),
    ],
)
def test_process_estimation_rejects_model_outside_scope(
    monkeypatch, training_updates, organization_id
):
    from apps.scientific.app.domains.execution import service_execution

    artifact_bytes = json.dumps({"prediction_value": 12.5}).encode()
    database = FakeInferenceDatabase(artifact_bytes)
    database.training_row.update(training_updates)
    monkeypatch.setattr(service_execution, "supabase", database)
    config = {
        "model_id": MODEL_ID,
        "scene_id": "scene-123",
        "points": [{"point_id": "p1"}],
    }

    asyncio.run(
        process_scientific_job(
            JOB_ID,
            "estimation",
            config,
            organization_id=organization_id,
        )
    )

    assert database.estimation_row["status"] == "failed"
    assert database.storage.bucket.downloaded_paths == []


def test_process_estimation_persists_failed_when_artifact_missing(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    database = FakeInferenceDatabase(
        json.dumps({"prediction_value": 12.5}).encode(),
        include_reference=False,
    )
    monkeypatch.setattr(service_execution, "supabase", database)
    config = {
        "model_id": MODEL_ID,
        "scene_id": "scene-123",
        "points": [{"point_id": "p1", "features": {}}],
    }

    asyncio.run(
        process_scientific_job(
            JOB_ID,
            "estimation",
            config,
            organization_id=ORGANIZATION_ID,
        )
    )

    assert database.estimation_row["status"] == "failed"
    assert database.estimation_row["result"] is None
    assert "artefacto" in database.estimation_row["error_message"].lower()


def test_process_estimation_persists_failed_when_storage_download_fails(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    database = FakeInferenceDatabase(
        json.dumps({"prediction_value": 12.5}).encode(),
        download_error=StorageException("storage unavailable"),
    )
    monkeypatch.setattr(service_execution, "supabase", database)

    asyncio.run(
        process_scientific_job(
            JOB_ID,
            "estimation",
            {
                "model_id": MODEL_ID,
                "scene_id": "scene-123",
                "points": [{"point_id": "p1"}],
            },
            organization_id=ORGANIZATION_ID,
        )
    )

    assert database.estimation_row["status"] == "failed"
    assert database.estimation_row["result"] is None
    assert database.storage.bucket.downloaded_paths == ["models/model-123/model.json"]


def test_process_estimation_persists_failed_when_checksum_is_invalid(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution

    database = FakeInferenceDatabase(json.dumps({"prediction_value": 12.5}).encode())
    database.training_row["result"]["model_artifact"]["checksum"] = "0" * 64
    monkeypatch.setattr(service_execution, "supabase", database)

    asyncio.run(
        process_scientific_job(
            JOB_ID,
            "estimation",
            {
                "model_id": MODEL_ID,
                "scene_id": "scene-123",
                "points": [{"point_id": "p1", "features": {}}],
            },
            organization_id=ORGANIZATION_ID,
        )
    )

    assert database.estimation_row["status"] == "failed"
    assert database.estimation_row["result"] is None
    assert "checksum" in database.estimation_row["error_message"].lower()
