import hashlib
import logging
import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-secret-token")

from apps.api.app.gateway import controller_gateway, service_gateway
from apps.api.app.main import app
from apps.scientific.app.core.dependencies import (
    require_authenticated_user,
    require_internal_service,
)
from apps.scientific.app.main import app as scientific_app

client = TestClient(app)

USER_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
ORGANIZATION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
DATASET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VERSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
AUTH_HEADERS = {
    "Authorization": "Bearer test-user-token",
    "X-Organization-ID": ORGANIZATION_ID,
}


def fake_authenticated_user(
    authorization: str | None = Header(default=None),
) -> dict:
    if authorization != "Bearer test-user-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado",
        )
    return {"sub": USER_ID}


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
        if self.table_name == "memberships":
            rows = [
                membership
                for membership in self.database.memberships
                if all(
                    str(
                        membership.get("organization_status")
                        if key == "organizations.status"
                        else membership.get(key)
                    )
                    == str(value)
                    for key, value in self.filters.items()
                )
            ]
            return SimpleNamespace(data=rows)

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

        if self.update_payload is not None:
            updated = []
            for row in self.database.jobs:
                if all(
                    str(row.get(column)) == value
                    for column, value in self.filters.items()
                ):
                    row.update(self.update_payload)
                    updated.append(row)
            return SimpleNamespace(data=updated)

        if self.insert_payload is not None:
            row = {
                **self.insert_payload,
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
                "result": None,
            }
            self.database.jobs.append(row)
            return SimpleNamespace(data=[row])

        rows = [
            dict(row)
            for row in self.database.jobs
            if all(
                str(row.get(column)) == value
                for column, value in self.filters.items()
            )
        ]
        return SimpleNamespace(data=rows)


class FakeStagingDatabase:
    def __init__(self):
        self.versions = [
            {
                "id": VERSION_ID,
                "dataset_id": DATASET_ID,
                "state": "PUBLISHED",
                "status": "published",
            }
        ]
        self.memberships = [
            {
                "user_id": USER_ID,
                "organization_id": ORGANIZATION_ID,
                "status": "active",
                "organization_status": "active",
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
def fake_staging_db(monkeypatch):
    database = FakeStagingDatabase()
    monkeypatch.setattr(
        "apps.api.app.gateway.executions_bridge.supabase", database
    )
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.controller_execution.supabase",
        database,
    )
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.supabase",
        database,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        require_authenticated_user,
        fake_authenticated_user,
    )
    return database


@pytest.mark.parametrize(
    "incoming_correlation_id",
    ["trace-training-123", None],
)
def test_web_training_bridge_dispatches_worker_and_persists_result(
    fake_staging_db,
    monkeypatch,
    caplog,
    incoming_correlation_id,
):
    caplog.set_level(logging.INFO)
    csv_data = b"clorofila_a\n10.0\n20.0\n30.0\n"
    checksum = hashlib.sha256(csv_data).hexdigest()
    fetch_file = MagicMock(return_value=(csv_data, checksum))
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.fetch_training_file",
        fetch_file,
    )

    request_headers = dict(AUTH_HEADERS)
    if incoming_correlation_id:
        request_headers["X-Correlation-ID"] = incoming_correlation_id

    submit_response = client.post(
        "/api/v1/executions/jobs",
        json={
            "dataset_version_id": VERSION_ID,
            "job_type": "TRAINING",
            "config": {
                "target_variable": "chlorophyll_a",
                "required_index": "NDCI",
            },
        },
        headers=request_headers,
    )

    assert submit_response.status_code == 202
    correlation_id = submit_response.headers["x-correlation-id"]
    if incoming_correlation_id:
        assert correlation_id == incoming_correlation_id
    else:
        uuid.UUID(correlation_id)
    assert any(
        record.name == "apps.api.app.main"
        and getattr(record, "correlation_id", None) == correlation_id
        for record in caplog.records
    )
    assert any(
        record.name == "apps.scientific.app.domains.execution.service_execution"
        and getattr(record, "correlation_id", None) == correlation_id
        and "Ejecución científica iniciada" in record.getMessage()
        for record in caplog.records
    )

    accepted = submit_response.json()
    job_id = accepted["job_id"]
    assert accepted["status"] == "queued"
    assert accepted["status_url"] == f"/api/v1/executions/{job_id}"

    status_response = client.get(
        f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS
    )
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["job_id"] == job_id
    assert status_data["job_type"] == "training"
    assert status_data["status"] == "completed"
    assert status_data["config"]["dataset_id"] == DATASET_ID
    assert status_data["config"]["version_id"] == VERSION_ID
    result = status_data["result"]
    assert result["model"] == "baseline"
    assert result["baseline"]["strategy"] == "mean_clorofila_a"
    assert result["baseline"]["train_sample_count"] == 2
    assert result["baseline"]["validation_sample_count"] == 1
    assert result["prediction_value"] == 15.0
    assert result["predictions"] == [15.0]
    assert result["metrics"] == {"mae": 15.0, "rmse": 15.0}
    assert result["version"] == VERSION_ID
    assert result["dataset_version_id"] == VERSION_ID
    assert result["model_version_id"] is None
    assert result["status"] == "completed"
    assert isinstance(result["warnings"], list)
    assert len(result["warnings"]) >= 1
    assert status_data["completed_at"] is not None
    fetch_file.assert_called_once_with(fake_staging_db, VERSION_ID)


@pytest.mark.parametrize(
    "incoming_correlation_id",
    ["trace-scientific-job-789", None],
)
def test_gateway_scientific_worker_execution_keeps_correlation_id(
    fake_staging_db,
    monkeypatch,
    caplog,
    incoming_correlation_id,
):
    caplog.set_level(logging.INFO)
    monkeypatch.setitem(
        scientific_app.dependency_overrides,
        require_authenticated_user,
        fake_authenticated_user,
    )
    monkeypatch.setitem(
        scientific_app.dependency_overrides,
        require_internal_service,
        lambda: None,
    )
    monkeypatch.setattr(
        controller_gateway.settings,
        "scientific_service_url",
        "http://scientific",
    )
    async_client_type = httpx.AsyncClient
    monkeypatch.setattr(
        service_gateway.httpx,
        "AsyncClient",
        lambda: async_client_type(
            transport=httpx.ASGITransport(app=scientific_app),
            base_url="http://scientific",
        ),
    )

    request_headers = {
        **AUTH_HEADERS,
        "X-Internal-Token": "test-secret-token",
    }
    if incoming_correlation_id:
        request_headers["X-Correlation-ID"] = incoming_correlation_id

    response = client.post(
        "/api/v1/scientific/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {
                "model_id": "88888888-8888-4888-8888-888888888888",
                "scene_id": "44444444-4444-4444-8444-444444444444",
            },
        },
        headers=request_headers,
    )

    assert response.status_code == 202
    correlation_id = response.headers["x-correlation-id"]
    if incoming_correlation_id:
        assert correlation_id == incoming_correlation_id
    else:
        uuid.UUID(correlation_id)

    assert any(
        record.name == "apps.api.app.main"
        and getattr(record, "correlation_id", None) == correlation_id
        for record in caplog.records
    )
    assert any(
        record.name == "apps.scientific.app.main"
        and getattr(record, "correlation_id", None) == correlation_id
        for record in caplog.records
    )
    assert any(
        record.name == "apps.scientific.app.domains.execution.service_execution"
        and getattr(record, "correlation_id", None) == correlation_id
        and "Ejecución científica iniciada" in record.getMessage()
        for record in caplog.records
    )
    assert fake_staging_db.jobs[0]["status"] == "completed"


def test_web_estimation_job_links_model_version_scene_and_requester(
    fake_staging_db,
):
    model_version_id = "88888888-8888-4888-8888-888888888888"
    scene_id = "44444444-4444-4444-8444-444444444444"
    response = client.post(
        "/api/v1/executions/jobs",
        json={
            "job_type": "ESTIMATION",
            "config": {"model_id": model_version_id, "scene_id": scene_id},
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert fake_staging_db.jobs[0]["model_version_id"] == model_version_id
    assert fake_staging_db.jobs[0]["scene_id"] == scene_id
    assert fake_staging_db.jobs[0]["requested_by"] == USER_ID


@pytest.mark.parametrize(
    "config",
    [
        {
            "model_id": "not-a-uuid",
            "scene_id": "44444444-4444-4444-8444-444444444444",
        },
        {
            "model_id": "88888888-8888-4888-8888-888888888888",
            "scene_id": "not-a-uuid",
        },
    ],
)
def test_web_estimation_rejects_non_uuid_model_or_scene(config, fake_staging_db):
    response = client.post(
        "/api/v1/executions/jobs",
        json={"job_type": "ESTIMATION", "config": config},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
    assert fake_staging_db.jobs == []


def test_web_training_bridge_rejects_unpublished_version(fake_staging_db):
    fake_staging_db.versions[0]["state"] = "DRAFT"

    response = client.post(
        "/api/v1/executions/jobs",
        json={
            "dataset_version_id": VERSION_ID,
            "job_type": "TRAINING",
            "config": {},
        },
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 409
    assert fake_staging_db.jobs == []


def test_cors_allows_organization_header_for_web_training():
    preflight = client.options(
        "/api/v1/executions/jobs",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-organization-id",
        },
    )

    assert preflight.status_code == 200
    allowed_headers = preflight.headers.get(
        "access-control-allow-headers", ""
    ).lower()
    assert "x-organization-id" in allowed_headers



