import os
from types import SimpleNamespace
from typing import Annotated

import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-secret-token")

from apps.scientific.app.core.dependencies import require_authenticated_user
from apps.scientific.app.domains.execution import (
    controller_execution,
    service_execution,
)
from apps.scientific.app.main import create_app

USER_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
ORGANIZATION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
OTHER_ORGANIZATION_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
OUTSIDER_ORGANIZATION_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"
JOB_ID = "11111111-1111-4111-8111-111111111111"
JOB_WITHOUT_ARTIFACT_ID = "22222222-2222-4222-8222-222222222222"
TAMPERED_JOB_ID = "33333333-3333-4333-8333-333333333333"
FOREIGN_JOB_ID = "44444444-4444-4444-8444-444444444444"
UNKNOWN_JOB_ID = "99999999-9999-4999-8999-999999999999"
ARTIFACT_PATH = f"models/{JOB_ID}/model.pkl"
FOREIGN_ARTIFACT_PATH = f"models/{FOREIGN_JOB_ID}/model.pkl"
AUTH_HEADERS = {
    "Authorization": "Bearer test-user-token",
    "X-Organization-ID": ORGANIZATION_ID,
}
MEMBERSHIPS = {
    (USER_ID, ORGANIZATION_ID),
    (USER_ID, OTHER_ORGANIZATION_ID),
}


def fake_authenticated_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    if authorization != "Bearer test-user-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado",
        )
    return {"sub": USER_ID}


class FakeStorageBucket:
    def __init__(self):
        self.calls = []

    def create_signed_url(self, path, expires_in):
        self.calls.append((path, expires_in))
        return {"signedURL": f"https://storage.test/sign/{path}?token=abc"}


class FakeStorage:
    def __init__(self):
        self.bucket = FakeStorageBucket()
        self.requested_buckets = []

    def from_(self, bucket):
        self.requested_buckets.append(bucket)
        return self.bucket


class FakeJobsQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters[column] = str(value)
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        return SimpleNamespace(
            data=[
                row
                for row in self.rows
                if all(str(row.get(c)) == v for c, v in self.filters.items())
            ]
        )


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.storage = FakeStorage()

    def table(self, table_name):
        assert table_name == "scientific_jobs"
        return FakeJobsQuery(self.rows)


def _artifact_reference(job_id, storage_path, checksum="a" * 64):
    return {
        "job_id": job_id,
        "bucket": "model_artifacts",
        "storage_path": storage_path,
        "checksum": checksum,
        "size_bytes": 12,
    }


@pytest.fixture
def env(monkeypatch):
    rows = [
        {
            "id": JOB_ID,
            "organization_id": ORGANIZATION_ID,
            "result": {"model_artifact": _artifact_reference(JOB_ID, ARTIFACT_PATH)},
        },
        {
            "id": JOB_WITHOUT_ARTIFACT_ID,
            "organization_id": ORGANIZATION_ID,
            "result": {"prediction_value": 15.0},
        },
        {
            "id": TAMPERED_JOB_ID,
            "organization_id": ORGANIZATION_ID,
            "result": {
                "model_artifact": _artifact_reference(
                    TAMPERED_JOB_ID, f"models/{FOREIGN_JOB_ID}/model.pkl"
                )
            },
        },
        {
            "id": FOREIGN_JOB_ID,
            "organization_id": OTHER_ORGANIZATION_ID,
            "result": {
                "model_artifact": _artifact_reference(
                    FOREIGN_JOB_ID, FOREIGN_ARTIFACT_PATH, checksum="b" * 64
                )
            },
        },
    ]
    database = FakeClient(rows)
    monkeypatch.setattr(controller_execution, "supabase", database)
    monkeypatch.setattr(
        service_execution,
        "has_active_organization_membership",
        lambda user_id, organization_id: (str(user_id), str(organization_id))
        in MEMBERSHIPS,
    )
    application = create_app()
    application.dependency_overrides[require_authenticated_user] = (
        fake_authenticated_user
    )
    try:
        yield SimpleNamespace(
            database=database,
            api=TestClient(application),
        )
    finally:
        application.dependency_overrides.clear()


def test_authorized_member_gets_temporary_signed_url(env):
    response = env.api.get(
        f"/api/v1/executions/{JOB_ID}/artifact", headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == JOB_ID
    assert body["download_url"] == f"https://storage.test/sign/{ARTIFACT_PATH}?token=abc"
    assert body["expires_in"] == 60
    assert body["checksum"] == "a" * 64
    assert body["size_bytes"] == 12
    assert response.headers["cache-control"] == "no-store"
    assert env.database.storage.requested_buckets == ["model_artifacts"]
    assert env.database.storage.bucket.calls == [(ARTIFACT_PATH, 60)]


def test_artifact_access_requires_authentication(env):
    response = env.api.get(
        f"/api/v1/executions/{JOB_ID}/artifact",
        headers={"X-Organization-ID": ORGANIZATION_ID},
    )

    assert response.status_code == 401
    assert env.database.storage.requested_buckets == []


def test_artifact_access_requires_organization_header(env):
    response = env.api.get(
        f"/api/v1/executions/{JOB_ID}/artifact",
        headers={"Authorization": AUTH_HEADERS["Authorization"]},
    )

    assert response.status_code == 422
    assert env.database.storage.requested_buckets == []


@pytest.mark.parametrize(
    "organization_id",
    [
        OTHER_ORGANIZATION_ID,  # miembro, pero el trabajo es de otra organización
        OUTSIDER_ORGANIZATION_ID,  # el usuario ni siquiera es miembro
    ],
)
def test_user_from_another_organization_cannot_access_artifact(env, organization_id):
    response = env.api.get(
        f"/api/v1/executions/{JOB_ID}/artifact",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": organization_id,
        },
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."
    assert "storage.test" not in response.text
    assert ARTIFACT_PATH not in response.text
    assert env.database.storage.requested_buckets == []


def test_artifact_access_is_isolated_bidirectionally_between_organizations(env):
    own_a = env.api.get(
        f"/api/v1/executions/{JOB_ID}/artifact", headers=AUTH_HEADERS
    )
    assert own_a.status_code == 200
    assert ARTIFACT_PATH in own_a.json()["download_url"]
    assert own_a.headers["x-correlation-id"]
    assert env.database.storage.bucket.calls == [(ARTIFACT_PATH, 60)]

    cross_a = env.api.get(
        f"/api/v1/executions/{FOREIGN_JOB_ID}/artifact", headers=AUTH_HEADERS
    )
    assert cross_a.status_code == 404
    assert cross_a.json()["message"] == "No se encontró el trabajo."
    assert FOREIGN_ARTIFACT_PATH not in cross_a.text
    assert "b" * 64 not in cross_a.text
    assert cross_a.headers["x-correlation-id"]
    assert env.database.storage.bucket.calls == [(ARTIFACT_PATH, 60)]

    foreign_headers = {
        "Authorization": AUTH_HEADERS["Authorization"],
        "X-Organization-ID": OTHER_ORGANIZATION_ID,
    }
    own_b = env.api.get(
        f"/api/v1/executions/{FOREIGN_JOB_ID}/artifact", headers=foreign_headers
    )
    assert own_b.status_code == 200
    assert FOREIGN_ARTIFACT_PATH in own_b.json()["download_url"]
    assert env.database.storage.bucket.calls == [
        (ARTIFACT_PATH, 60),
        (FOREIGN_ARTIFACT_PATH, 60),
    ]

    cross_b = env.api.get(
        f"/api/v1/executions/{JOB_ID}/artifact", headers=foreign_headers
    )
    assert cross_b.status_code == 404
    assert cross_b.json()["message"] == "No se encontró el trabajo."
    assert ARTIFACT_PATH not in cross_b.text
    assert "a" * 64 not in cross_b.text
    assert cross_b.headers["x-correlation-id"]
    assert env.database.storage.bucket.calls == [
        (ARTIFACT_PATH, 60),
        (FOREIGN_ARTIFACT_PATH, 60),
    ]

def test_unknown_job_returns_404(env):
    response = env.api.get(
        f"/api/v1/executions/{UNKNOWN_JOB_ID}/artifact", headers=AUTH_HEADERS
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."
    assert env.database.storage.requested_buckets == []


def test_job_without_artifact_returns_404(env):
    response = env.api.get(
        f"/api/v1/executions/{JOB_WITHOUT_ARTIFACT_ID}/artifact",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el artefacto."
    assert env.database.storage.requested_buckets == []


def test_reference_pointing_to_another_job_is_not_signed(env):
    response = env.api.get(
        f"/api/v1/executions/{TAMPERED_JOB_ID}/artifact", headers=AUTH_HEADERS
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el artefacto."
    assert env.database.storage.bucket.calls == []


def test_storage_failure_returns_503_without_leaking_details(env, monkeypatch):
    def failing_sign(_path, _expires_in):
        raise RuntimeError("detalle interno de storage")

    monkeypatch.setattr(env.database.storage.bucket, "create_signed_url", failing_sign)

    response = env.api.get(
        f"/api/v1/executions/{JOB_ID}/artifact", headers=AUTH_HEADERS
    )

    assert response.status_code == 503
    assert "detalle interno" not in response.text
