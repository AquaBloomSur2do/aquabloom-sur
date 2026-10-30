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
INTERNAL_HEADERS = {"X-Internal-Token": "test-secret-token"}
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


class FakeQuery:
    def __init__(self, table_name, state):
        self.table_name = table_name
        self.state = state
        self.filters = {}
        self.inserted = None

    def select(self, _columns):
        return self

    def insert(self, payload):
        self.inserted = payload
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _count):
        return self

    def execute(self):
        if self.table_name == "scientific_jobs":
            if self.inserted is not None:
                job = {
                    **self.inserted,
                    "id": JOB_ID,
                    "result": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
                self.state["job"] = job
                return SimpleNamespace(data=[job])
            job = self.state.get("job")
            if job and str(job["id"]) == self.filters.get("id"):
                return SimpleNamespace(data=[job])
            return SimpleNamespace(data=[])
        if self.table_name == "memberships":
            if self.state.get("membership") and (
                self.filters.get("user_id") == USER_ID
                and self.filters.get("organization_id") == ORGANIZATION_ID
                and self.filters.get("status") == "active"
            ):
                return SimpleNamespace(data=[{"id": str(uuid4())}])
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=[])


class FakeSupabase:
    def __init__(self, state):
        self.state = state

    def table(self, table_name):
        return FakeQuery(table_name, self.state)


@pytest.fixture
def execution_client(monkeypatch):
    settings.internal_service_token = SecretStr("test-secret-token")
    state = {"membership": True}
    monkeypatch.setattr(execution_module, "supabase", FakeSupabase(state))
    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: {"sub": USER_ID},
    )
    yield TestClient(app), state
    app.dependency_overrides.clear()


def test_create_execution_job_returns_202(execution_client):
    client, _state = execution_client
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
    assert data["status"] == "pending"
    assert data["job_id"] in data["status_url"]


def test_get_job_status_returns_200_for_organization_member(execution_client):
    client, state = execution_client
    state["job"] = {
        "id": JOB_ID,
        "organization_id": ORGANIZATION_ID,
        "status": "completed",
        "result": {"accuracy": 0.95},
        "created_at": datetime.now(UTC).isoformat(),
    }

    response = client.get(
        f"/api/v1/executions/{JOB_ID}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == JOB_ID
    assert response.json()["status"] == "completed"
    assert response.json()["result"] == {"accuracy": 0.95}


def test_get_job_status_returns_403_for_another_organization(execution_client):
    client, state = execution_client
    state["membership"] = False
    state["job"] = {
        "id": JOB_ID,
        "organization_id": ORGANIZATION_ID,
        "status": "running",
        "result": None,
        "created_at": datetime.now(UTC).isoformat(),
    }

    response = client.get(f"/api/v1/executions/{JOB_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 403


def test_get_job_status_returns_404_for_missing_job(execution_client):
    client, _state = execution_client

    response = client.get(f"/api/v1/executions/{JOB_ID}", headers=AUTH_HEADERS)

    assert response.status_code == 404


def test_create_execution_job_rejects_invalid_payload(execution_client):
    client, _state = execution_client
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
    client, _state = execution_client
    payload = {
        "job_type": "estimation",
        "organization_id": ORGANIZATION_ID,
        "config": {"model_id": "model_v1", "scene_id": "scene_001"},
    }

    response = client.post("/api/v1/executions/", json=payload)

    assert response.status_code == 401
