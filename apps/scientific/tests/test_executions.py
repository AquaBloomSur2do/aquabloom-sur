import asyncio
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import SecretStr

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-secret-token")

from apps.scientific.app.core.config import settings as scientific_settings
from apps.scientific.app.core.dependencies import require_authenticated_user
from apps.scientific.app.domains.execution import (
    controller_execution,
    service_execution,
)
from apps.scientific.app.domains.execution.domain_execution import (
    MAX_ERROR_MESSAGE_LENGTH,
    JobLimitExceededError,
    calculate_baseline,
    parse_training_csv,
    resolve_job_timeout,
)
from apps.scientific.app.domains.execution.model_artifacts import (
    save_model_artifact,
)
from apps.scientific.app.domains.execution.model_execution import (
    fetch_training_file,
)
from apps.scientific.app.domains.execution.service_execution import (
    process_scientific_job,
)
from apps.scientific.app.main import app, create_app

client = TestClient(app)

USER_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
ORGANIZATION_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
OTHER_ORGANIZATION_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
AUTH_HEADERS = {
    "Authorization": "Bearer test-user-token",
    "X-Organization-ID": ORGANIZATION_ID,
}
HEADERS = {**AUTH_HEADERS, "X-Internal-Token": "test-secret-token"}
DATASET_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VERSION_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
MODEL_VERSION_ID = "11111111-2222-4333-8444-555555555555"
OTHER_MODEL_VERSION_ID = "22222222-3333-4444-8555-666666666666"
SCENE_ID = "33333333-4444-4555-8666-777777777777"
OTHER_SCENE_ID = "44444444-5555-4666-8777-888888888888"


def fake_authenticated_user(
    authorization: str | None = Header(default=None),
) -> dict:
    if authorization != "Bearer test-user-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado",
        )
    return {"sub": USER_ID}


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
            return FakeResponse(rows)

        # 1. Esquema dataset - tabla versions (S2-147)
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

        # 2. Esquema por defecto - tabla scientific_jobs (S2-150 / S2-149)
        if self.table_name != "scientific_jobs":
            raise AssertionError(f"Unexpected table: {self.table_name}")

        if self.update_payload is not None:
            updated_rows = []
            for row in self.database.rows:
                if all(
                    str(row.get(column)) == value
                    for column, value in self.filters.items()
                ):
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
                raise APIError(
                    {"code": "23505", "message": "unique constraint violation"}
                )

            if idempotency_key and any(
                row.get("idempotency_key") == idempotency_key
                and row.get("organization_id")
                == self.insert_payload.get("organization_id")
                for row in self.database.rows
            ):
                raise APIError(
                    {"code": "23505", "message": "unique constraint violation"}
                )

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
            if all(
                str(row.get(column)) == value for column, value in self.filters.items()
            )
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
        self.memberships = [
            {
                "user_id": USER_ID,
                "organization_id": ORGANIZATION_ID,
                "status": "active",
                "organization_status": "active",
            },
            {
                "user_id": USER_ID,
                "organization_id": OTHER_ORGANIZATION_ID,
                "status": "active",
                "organization_status": "active",
            },
        ]

    def schema(self, schema_name):
        return SimpleNamespace(
            table=lambda table_name: FakeQuery(self, schema_name, table_name)
        )

    def table(self, table_name):
        return FakeQuery(self, None, table_name)


@pytest.fixture(autouse=True)
def fake_database(monkeypatch):
    database = FakeDatabase()
    monkeypatch.setattr(
        scientific_settings,
        "internal_service_token",
        SecretStr("test-secret-token"),
    )
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.controller_execution.supabase",
        database,
    )
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.supabase",
        database,
    )
    monkeypatch.setattr(
        service_execution,
        "has_active_organization_membership",
        lambda user_id, organization_id: any(
            membership["user_id"] == str(user_id)
            and membership["organization_id"] == str(organization_id)
            and membership["status"] == "active"
            and membership["organization_status"] == "active"
            for membership in database.memberships
        ),
    )
    monkeypatch.setattr(
        service_execution,
        "get_dataset_version_for_training",
        lambda version_id, organization_id: next(
            (
                version
                for version in database.versions
                if version["id"] == str(version_id)
                and str(organization_id) == ORGANIZATION_ID
            ),
            None,
        ),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        require_authenticated_user,
        fake_authenticated_user,
    )
    return database


def estimation_payload(model_id=MODEL_VERSION_ID, scene_id=SCENE_ID):
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
# PRUEBAS S2-148 Y S2-149: IDEMPOTENCIA Y FLUJO BASE
# =========================================================


def test_create_execution_job_returns_202(fake_database):
    response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=HEADERS
    )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["status_url"] == f"/api/v1/executions/{data['job_id']}"
    job = fake_database.rows[0]
    assert job["model_version_id"] == MODEL_VERSION_ID
    assert job["scene_id"] == SCENE_ID
    assert job["requested_by"] == USER_ID


def test_scientific_service_echoes_and_generates_correlation_id():
    response = client.get(
        "/",
        headers={"X-Correlation-ID": "trace-scientific-123"},
    )
    generated_response = client.get("/")

    assert response.headers["x-correlation-id"] == "trace-scientific-123"
    assert generated_response.headers["x-correlation-id"]
    uuid.UUID(generated_response.headers["x-correlation-id"])


def test_scientific_cors_preserves_internal_headers_and_exposes_correlation_id():
    preflight = client.options(
        "/api/v1/executions/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "authorization,content-type,x-idempotency-key,"
                "x-internal-token,x-organization-id,x-correlation-id,x-request-id"
            ),
        },
    )

    assert preflight.status_code == 200
    allowed_headers = preflight.headers.get("access-control-allow-headers", "").lower()
    assert "x-idempotency-key" in allowed_headers
    assert "x-internal-token" in allowed_headers
    assert "x-organization-id" in allowed_headers
    assert "x-correlation-id" in allowed_headers
    assert "x-request-id" in allowed_headers

    response = client.get(
        "/",
        headers={"Origin": "http://localhost:5173"},
    )
    assert (
        response.headers.get("access-control-expose-headers", "").lower()
        == "x-correlation-id"
    )


def test_get_job_status_returns_200(fake_database):
    post_response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=HEADERS
    )
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    response = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id

    assert data["status"] == "completed"
    assert data["model_version_id"] == MODEL_VERSION_ID
    assert data["scene_id"] == SCENE_ID
    assert data["requested_by"] == USER_ID

    assert fake_database.rows[0]["organization_id"] == ORGANIZATION_ID
    assert fake_database.rows[0]["requested_by"] == USER_ID
    assert len(fake_database.rows) == 1


def test_get_job_status_returns_404_for_invalid_id(fake_database):
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/executions/{fake_uuid}", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."


def test_get_job_status_returns_404_for_another_organization(fake_database):
    create_response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=HEADERS
    )
    job_id = create_response.json()["job_id"]
    fake_database.rows[0]["result"] = {
        "pilot_result": "resultado confidencial",
        "predictions": [12.5],
    }

    response = client.get(
        f"/api/v1/executions/{job_id}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": OTHER_ORGANIZATION_ID,
        },
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."
    assert "resultado confidencial" not in response.text


def test_job_status_is_isolated_bidirectionally_between_organizations(fake_database):
    def create_job(organization_id):
        response = client.post(
            "/api/v1/executions/",
            json=estimation_payload(),
            headers={
                "Authorization": AUTH_HEADERS["Authorization"],
                "X-Organization-ID": organization_id,
                "X-Internal-Token": "test-secret-token",
            },
        )
        assert response.status_code == 202
        return response.json()["job_id"]

    job_a = create_job(ORGANIZATION_ID)
    job_b = create_job(OTHER_ORGANIZATION_ID)
    assert job_a != job_b

    results = {
        job_a: {"prediction_value": 11.1, "confidential_marker": "org-a-secret"},
        job_b: {"prediction_value": 22.2, "confidential_marker": "org-b-secret"},
    }
    for row in fake_database.rows:
        if row["id"] in results:
            row["result"] = results[row["id"]]

    own_a = client.get(f"/api/v1/executions/{job_a}", headers=AUTH_HEADERS)
    assert own_a.status_code == 200
    assert own_a.json()["result"]["confidential_marker"] == "org-a-secret"
    assert own_a.headers["x-correlation-id"]

    cross_a = client.get(
        f"/api/v1/executions/{job_b}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": ORGANIZATION_ID,
        },
    )
    assert cross_a.status_code == 404
    assert cross_a.json()["message"] == "No se encontró el trabajo."
    assert "org-b-secret" not in cross_a.text
    assert "22.2" not in cross_a.text
    assert cross_a.headers["x-correlation-id"]

    own_b = client.get(
        f"/api/v1/executions/{job_b}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": OTHER_ORGANIZATION_ID,
        },
    )
    assert own_b.status_code == 200
    assert own_b.json()["result"]["confidential_marker"] == "org-b-secret"

    cross_b = client.get(
        f"/api/v1/executions/{job_a}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": OTHER_ORGANIZATION_ID,
        },
    )
    assert cross_b.status_code == 404
    assert cross_b.json()["message"] == "No se encontró el trabajo."
    assert "org-a-secret" not in cross_b.text
    assert "11.1" not in cross_b.text
    assert cross_b.headers["x-correlation-id"]

def test_get_job_status_requires_authentication(fake_database):
    response = client.get(
        f"/api/v1/executions/{uuid.uuid4()}",
        headers={"X-Organization-ID": ORGANIZATION_ID},
    )

    assert response.status_code == 401


def test_create_execution_job_rejects_non_member_organization(fake_database):
    headers = {
        "Authorization": AUTH_HEADERS["Authorization"],
        "X-Organization-ID": "ffffffff-ffff-4fff-8fff-ffffffffffff",
        "X-Internal-Token": "test-secret-token",
    }

    response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=headers
    )

    assert response.status_code == 404
    assert fake_database.rows == []


def test_idempotency_keys_are_scoped_to_organization(fake_database):
    idempotency_headers = {
        **HEADERS,
        "X-Idempotency-Key": "same-key-in-different-organizations",
    }
    first = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers=idempotency_headers,
    )
    second = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers={
            **idempotency_headers,
            "X-Organization-ID": OTHER_ORGANIZATION_ID,
        },
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(fake_database.rows) == 2


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
    first = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=headers
    )
    second = client.post(
        "/api/v1/executions/",
        json=estimation_payload(
            model_id=OTHER_MODEL_VERSION_ID,
            scene_id=OTHER_SCENE_ID,
        ),
        headers=headers,
    )

    assert first.status_code == 202
    assert second.status_code == 409
    assert len(fake_database.rows) == 1


def test_concurrent_idempotent_insert_returns_existing_job(fake_database):
    fake_database.race_on_insert = True
    headers = {**HEADERS, "X-Idempotency-Key": "test-idem-race"}
    response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=headers
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == fake_database.rows[0]["id"]
    assert len(fake_database.rows) == 1


def test_requests_without_idempotency_key_create_distinct_jobs(fake_database):
    payload = estimation_payload(scene_id=OTHER_SCENE_ID)
    first = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    second = client.post("/api/v1/executions/", json=payload, headers=HEADERS)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(fake_database.rows) == 2


def test_empty_idempotency_key_is_rejected(fake_database):
    headers = {**HEADERS, "X-Idempotency-Key": "   "}
    response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=headers
    )
    assert response.status_code == 422


# =========================================================
# PRUEBAS S2-150: FALLOS, TIMEOUTS, LÍMITES Y CONSULTABILIDAD
# =========================================================


def test_execution_job_handles_internal_exception(monkeypatch, fake_database):
    """Una excepción persiste FAILED y expone el error consultable vía API (S2-150)."""

    async def fail_internally(*_args, **_kwargs):
        raise RuntimeError(
            "Excepción interna: Fallo al procesar los tensores de la escena."
        )

    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.run_scientific_algorithm",
        fail_internally,
    )
    payload = estimation_payload()

    post_response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    first_get = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    second_get = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)

    assert first_get.status_code == 200
    assert second_get.status_code == 200
    data = first_get.json()
    assert data["job_id"] == job_id
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["completed_at"] is not None
    assert (
        data["error_message"]
        == "Excepción interna: Fallo al procesar los tensores de la escena."
    )


def test_execution_job_handles_timeout_exceeded(monkeypatch, fake_database):
    """El timeout excedido aborta el trabajo, persiste FAILED y es consultable (S2-150)."""
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.JOB_TIMEOUT_SECONDS",
        0.1,
    )

    payload = estimation_payload()
    post_response = client.post("/api/v1/executions/", json=payload, headers=HEADERS)
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    status_response = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["completed_at"] is not None
    assert "Timeout de 0.1s" in data["error_message"]


def test_execution_job_handles_limit_exceeded_error(monkeypatch, fake_database):
    """Un límite operativo excedido deja estado failed y mensaje claro consultable."""

    async def fail_with_limit(*_args, **_kwargs):
        raise JobLimitExceededError("Máximo de 500000 píxeles superado.")

    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.run_scientific_algorithm",
        fail_with_limit,
    )

    post_response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=HEADERS
    )
    job_id = post_response.json()["job_id"]

    status_response = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["status"] == "failed"
    assert data["result"] is None
    assert data["completed_at"] is not None
    assert "Límite de ejecución excedido" in data["error_message"]
    assert "500000 píxeles" in data["error_message"]


def test_execution_job_handles_empty_exception_with_fallback_message(
    monkeypatch, fake_database
):
    """Una excepción sin texto siempre persiste un mensaje descriptivo consultable."""

    async def fail_silently(*_args, **_kwargs):
        raise RuntimeError()

    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.run_scientific_algorithm",
        fail_silently,
    )

    post_response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=HEADERS
    )
    job_id = post_response.json()["job_id"]

    status_response = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["status"] == "failed"
    assert "RuntimeError" in data["error_message"]


def test_execution_job_truncates_oversized_error_message(monkeypatch, fake_database):
    """Mensajes de error extensos se acotan sin romper la persistencia ni la consulta."""

    async def fail_with_huge_message(*_args, **_kwargs):
        raise RuntimeError("fallo " * 400)

    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.run_scientific_algorithm",
        fail_with_huge_message,
    )

    post_response = client.post(
        "/api/v1/executions/", json=estimation_payload(), headers=HEADERS
    )
    job_id = post_response.json()["job_id"]

    status_response = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    assert status_response.status_code == 200
    error_message = status_response.json()["error_message"]
    assert len(error_message) <= MAX_ERROR_MESSAGE_LENGTH
    assert error_message.endswith("...")


def test_execution_job_persists_failed_state_on_cancellation(
    monkeypatch, fake_database
):
    """Una cancelación del worker deja el trabajo en failed y relanza CancelledError."""
    job_id = str(uuid.uuid4())
    config = {"model_id": MODEL_VERSION_ID, "scene_id": SCENE_ID}
    fake_database.rows.append(
        {
            "id": job_id,
            "job_type": "estimation",
            "config": config,
            "status": "queued",
            "organization_id": ORGANIZATION_ID,
            "requested_by": USER_ID,
            "result": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    async def cancel_algorithm(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.run_scientific_algorithm",
        cancel_algorithm,
    )

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(process_scientific_job(job_id, "estimation", config))

    status_response = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["status"] == "failed"
    assert data["completed_at"] is not None
    assert "cancelada" in data["error_message"].lower()


def test_failed_job_error_is_isolated_by_organization(monkeypatch, fake_database):
    """El error de un trabajo fallido solo es consultable por su organización."""

    async def fail_internally(*_args, **_kwargs):
        raise RuntimeError("Fallo aislado por organización.")

    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.run_scientific_algorithm",
        fail_internally,
    )

    post_response = client.post(
        "/api/v1/executions/",
        json=estimation_payload(),
        headers=HEADERS,
    )
    job_id = post_response.json()["job_id"]
    assert fake_database.rows[0]["status"] == "failed"

    other_org_response = client.get(
        f"/api/v1/executions/{job_id}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": OTHER_ORGANIZATION_ID,
        },
    )
    assert other_org_response.status_code == 404


@pytest.mark.parametrize("invalid_timeout", [0, -1, float("nan"), float("inf")])
def test_resolve_job_timeout_rejects_invalid_values(invalid_timeout):
    with pytest.raises(ValueError, match="tiempo máximo"):
        resolve_job_timeout(invalid_timeout)


# =========================================================
# PRUEBAS S2-147: VALIDACION DE TRAINING (BARBARA)
# =========================================================


def test_training_requires_a_published_dataset_version(fake_database):
    fake_database.versions[0]["state"] = "APPROVED"
    response = client.post(
        "/api/v1/executions/", json=training_payload(), headers=HEADERS
    )
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


# =========================================================
# PRUEBAS S2-155: BASELINE Y FLUJOS CON MOCKS
# =========================================================


def mock_training_file(monkeypatch, csv_content: bytes, valid_checksum: bool = True):
    checksum = hashlib.sha256(csv_content).hexdigest() if valid_checksum else "0" * 64
    fetch_file = MagicMock(return_value=(csv_content, checksum))
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.fetch_training_file",
        fetch_file,
    )
    return fetch_file


def test_model_fetches_training_file_for_version(monkeypatch):
    mock_client = MagicMock()
    expected_checksum = "a" * 64
    csv_content = b"clorofila_a\n10.0\n"
    mock_client.download_training_file.return_value = (
        csv_content,
        expected_checksum,
    )
    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.model_execution.CoreServiceClient",
        lambda: mock_client,
    )

    assert fetch_training_file(VERSION_ID, ORGANIZATION_ID, USER_ID) == (
        csv_content,
        expected_checksum,
    )
    mock_client.download_training_file.assert_called_once_with(
        VERSION_ID,
        ORGANIZATION_ID,
        USER_ID,
    )


def test_training_is_persisted_as_queued_and_returns_202(fake_database, monkeypatch):
    csv_data = b"clorofila_a\n10.0\n20.0\n30.0\n"
    fetch_file = mock_training_file(monkeypatch, csv_data)
    response = client.post(
        "/api/v1/executions/", json=training_payload(), headers=HEADERS
    )
    assert response.status_code == 202
    assert fake_database.rows[0]["status"] == "completed"
    result = fake_database.rows[0]["result"]
    assert result["prediction_value"] == 15.0
    assert result["predictions"] == [15.0]
    assert result["metrics"] == {"mae": 15.0, "rmse": 15.0}
    fetch_file.assert_called_once_with(
        VERSION_ID,
        uuid.UUID(ORGANIZATION_ID),
        uuid.UUID(USER_ID),
    )


def test_parse_training_csv_rechaza_checksum_invalido():
    csv_data = b"clorofila_a\n10.0\n"
    with pytest.raises(ValueError, match="Checksum"):
        parse_training_csv(csv_data, "0" * 64)


def test_parse_training_csv_rechaza_valores_invalidos():
    csv_data = b"clorofila_a\n10.0\nNA\n30.0\n"
    with pytest.raises(ValueError, match="no num"):
        parse_training_csv(csv_data, hashlib.sha256(csv_data).hexdigest())


@pytest.mark.parametrize(
    ("csv_data", "message"),
    [
        (b"", "vacío"),
        (b"\xff\xfe", "UTF-8"),
        (b"temperatura\n10\n", "columna objetivo"),
        (b"clorofila_a\nNaN\n", "no num"),
        (b"clorofila_a\nInf\n", "no num"),
    ],
)
def test_parse_training_csv_rechaza_insumos_invalidos(csv_data, message):
    with pytest.raises(ValueError, match=message):
        parse_training_csv(csv_data, hashlib.sha256(csv_data).hexdigest())


def test_baseline_evaluacion_no_modifica_media():
    train_data = [{"clorofila_a": 10.0}, {"clorofila_a": 20.0}]
    val_data = [{"clorofila_a": 100.0}, {"clorofila_a": 200.0}]
    result = calculate_baseline(train_data, val_data)
    assert result["prediction_value"] == 15.0
    assert result["predictions"] == [15.0, 15.0]
    assert result["metrics"]["mae"] == 135.0


def test_baseline_falla_con_particiones_vacias():
    with pytest.raises(ValueError, match="entrenamiento vacío"):
        calculate_baseline([], [{"clorofila_a": 10.0}])
    with pytest.raises(ValueError, match="evaluación vacío"):
        calculate_baseline([{"clorofila_a": 10.0}], [])


def test_get_training_job_status_exposes_full_structured_result(
    fake_database, monkeypatch
):
    monkeypatch.setattr(scientific_settings, "environment", "staging")
    monkeypatch.setenv("APP_VERSION", "test-build-158")
    csv_data = b"clorofila_a\n10.0\n20.0\n30.0\n"
    mock_training_file(monkeypatch, csv_data)

    post_response = client.post(
        "/api/v1/executions/", json=training_payload(), headers=HEADERS
    )
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    get_response = client.get(f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS)
    assert get_response.status_code == 200
    body = get_response.json()

    assert body["job_id"] == job_id
    assert body["status"] == "completed"
    assert body["dataset_version_id"] == VERSION_ID

    result = body["result"]
    assert result["model"] == "baseline"
    assert result["baseline"]["strategy"] == "mean_clorofila_a"
    assert result["baseline"]["train_sample_count"] == 2
    assert result["baseline"]["validation_sample_count"] == 1
    assert result["metrics"] == {"mae": 15.0, "rmse": 15.0}
    assert result["version"] == VERSION_ID
    assert result["dataset_version_id"] == VERSION_ID
    assert result["status"] == "completed"
    assert isinstance(result["warnings"], list)
    assert len(result["warnings"]) >= 1
    assert result["reproducibility"] == {
        "dataset_version_id": VERSION_ID,
        "partition": {
            "strategy": "sequential",
            "split_ratio": 0.8,
            "train_sample_count": 2,
            "validation_sample_count": 1,
        },
        "seed": None,
        "configuration": {
            "algorithm": "baseline",
            "baseline_strategy": "mean_clorofila_a",
            "training_config": {
                "dataset_id": DATASET_ID,
                "version_id": VERSION_ID,
                "epochs": 50,
                "learning_rate": 0.01,
            },
            "split_strategy": "sequential",
            "split_ratio": 0.8,
        },
        "code_version": "test-build-158",
        "environment": "staging",
    }


# =========================================================
# PRUEBA S2-167: PERSISTENCIA Y RECUPERACIÓN TRAS REINICIO
# =========================================================


def _init_persistent_sqlite_db(db_path: Path) -> None:
    """Inicializa en disco el esquema de scientific_jobs (migraciones 022, 023 y 027)."""
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE scientific_jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL CHECK (job_type IN ('training', 'modeling', 'estimation')),
                config TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
                result TEXT,
                error_message TEXT,
                idempotency_key TEXT,
                organization_id TEXT,
                requested_by TEXT,
                dataset_version_id TEXT,
                model_version_id TEXT,
                scene_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                started_at TEXT,
                completed_at TEXT
            );

            CREATE UNIQUE INDEX uq_scientific_jobs_idempotency_key
                ON scientific_jobs (organization_id, idempotency_key)
                WHERE idempotency_key IS NOT NULL AND organization_id IS NOT NULL;

            CREATE TABLE memberships (
                user_id TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                status TEXT NOT NULL,
                organization_status TEXT NOT NULL
            );

            CREATE TABLE dataset_versions (
                id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                state TEXT NOT NULL,
                status TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO memberships (user_id, organization_id, status, organization_status)
            VALUES (?, ?, 'active', 'active')
            """,
            [
                (USER_ID, ORGANIZATION_ID),
                (USER_ID, OTHER_ORGANIZATION_ID),
            ],
        )
        conn.execute(
            """
            INSERT INTO dataset_versions (id, dataset_id, state, status)
            VALUES (?, ?, 'PUBLISHED', 'PUBLISHED')
            """,
            (VERSION_ID, DATASET_ID),
        )


class _PersistentSqliteQuery:
    def __init__(self, db_path: Path, schema_name: str | None, table_name: str):
        self.db_path = db_path
        self.schema_name = schema_name
        self.table_name = table_name
        self.filters: dict[str, str] = {}
        self.insert_payload: dict[str, object] | None = None
        self.update_payload: dict[str, object] | None = None
        self.limit_value: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column: str, value: object):
        self.filters[column] = str(value)
        return self

    def limit(self, count: int):
        self.limit_value = count
        return self

    def insert(self, payload: dict[str, object]):
        self.insert_payload = dict(payload)
        return self

    def update(self, payload: dict[str, object]):
        self.update_payload = dict(payload)
        return self

    def _resolve_table_and_filters(self) -> tuple[str, dict[str, str]]:
        if self.schema_name == "dataset" and self.table_name == "versions":
            return "dataset_versions", dict(self.filters)
        if self.table_name == "memberships":
            mapped = {
                ("organization_status" if key == "organizations.status" else key): value
                for key, value in self.filters.items()
            }
            return "memberships", mapped
        return self.table_name, dict(self.filters)

    @staticmethod
    def _serialize_value(column: str, value: object) -> object:
        if column in {"config", "result"} and value is not None:
            return json.dumps(value)
        return value

    @staticmethod
    def _deserialize_row(row: sqlite3.Row) -> dict[str, object]:
        record = dict(row)
        for json_col in ("config", "result"):
            raw = record.get(json_col)
            if isinstance(raw, str):
                record[json_col] = json.loads(raw)
        return record

    def execute(self):
        sql_table, mapped_filters = self._resolve_table_and_filters()
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.row_factory = sqlite3.Row

            if self.insert_payload is not None:
                row = dict(self.insert_payload)
                row.setdefault("id", str(uuid.uuid4()))
                row.setdefault("created_at", datetime.now(UTC).isoformat())
                row.setdefault("result", None)
                columns = list(row.keys())
                values = [self._serialize_value(col, row[col]) for col in columns]
                placeholders = ", ".join("?" for _ in columns)
                col_names = ", ".join(columns)
                conn.execute(
                    f"INSERT INTO {sql_table} ({col_names}) VALUES ({placeholders})",
                    values,
                )
                return FakeResponse([row])

            where_clauses = [f"{col} = ?" for col in mapped_filters]
            where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            filter_values = list(mapped_filters.values())

            if self.update_payload is not None:
                updates = dict(self.update_payload)
                updates.setdefault("updated_at", datetime.now(UTC).isoformat())
                set_clauses = [f"{col} = ?" for col in updates]
                set_values = [
                    self._serialize_value(col, updates[col]) for col in updates
                ]
                conn.execute(
                    f"UPDATE {sql_table} SET {', '.join(set_clauses)}{where_sql}",
                    [*set_values, *filter_values],
                )
                cursor = conn.execute(
                    f"SELECT * FROM {sql_table}{where_sql}", filter_values
                )
                return FakeResponse(
                    [self._deserialize_row(r) for r in cursor.fetchall()]
                )

            limit_sql = (
                f" LIMIT {int(self.limit_value)}"
                if self.limit_value is not None
                else ""
            )
            cursor = conn.execute(
                f"SELECT * FROM {sql_table}{where_sql}{limit_sql}",
                filter_values,
            )
            return FakeResponse([self._deserialize_row(r) for r in cursor.fetchall()])


class PersistentSqliteClient:
    """Cliente de base de datos respaldado por archivo SQLite en disco."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def schema(self, schema_name: str):
        return SimpleNamespace(
            table=lambda table_name: _PersistentSqliteQuery(
                self.db_path, schema_name, table_name
            )
        )

    def table(self, table_name: str):
        return _PersistentSqliteQuery(self.db_path, None, table_name)


def test_job_status_and_result_persist_across_api_restart(tmp_path, monkeypatch):
    """Tras reiniciar la API, el estado y resultado completados siguen disponibles (S2-167)."""
    db_path = tmp_path / "scientific_persistent.db"
    _init_persistent_sqlite_db(db_path)

    csv_data = b"clorofila_a\n10.0\n20.0\n30.0\n"
    checksum = hashlib.sha256(csv_data).hexdigest()

    first_app = create_app()
    restarted_app = create_app()

    try:
        # 1. Primera instancia de la API conectada a almacenamiento persistente en disco
        first_db_client = PersistentSqliteClient(db_path)
        monkeypatch.setattr(controller_execution, "supabase", first_db_client)
        monkeypatch.setattr(service_execution, "supabase", first_db_client)
        first_app.dependency_overrides[require_authenticated_user] = (
            fake_authenticated_user
        )

        with monkeypatch.context() as mp:
            mp.setattr(
                service_execution,
                "fetch_training_file",
                lambda _version_id, _organization_id, _user_id: (
                    csv_data,
                    checksum,
                ),
            )
            with TestClient(first_app) as first_api_client:
                create_response = first_api_client.post(
                    "/api/v1/executions/",
                    json=training_payload(),
                    headers=HEADERS,
                )
                assert create_response.status_code == 202
                job_id = create_response.json()["job_id"]

                initial_status = first_api_client.get(
                    f"/api/v1/executions/{job_id}",
                    headers=AUTH_HEADERS,
                )
                assert initial_status.status_code == 200
                initial_body = initial_status.json()
                assert initial_body["status"] == "completed"
                assert initial_body["result"] is not None

        # 2. Descartar la primera instancia y crear un cliente limpio tras el reinicio
        first_app.dependency_overrides.clear()
        restarted_db_client = PersistentSqliteClient(db_path)
        monkeypatch.setattr(controller_execution, "supabase", restarted_db_client)
        monkeypatch.setattr(service_execution, "supabase", restarted_db_client)
        restarted_app.dependency_overrides[require_authenticated_user] = (
            fake_authenticated_user
        )

        # 3. Consultar el mismo job_id en la nueva instancia sin mockear fetch_training_file
        with TestClient(restarted_app) as restarted_api_client:
            recovered_response = restarted_api_client.get(
                f"/api/v1/executions/{job_id}",
                headers=AUTH_HEADERS,
            )
            assert recovered_response.status_code == 200
            recovered_body = recovered_response.json()

            assert recovered_body == initial_body
            assert recovered_body["job_id"] == job_id
            assert recovered_body["job_type"] == "training"
            assert recovered_body["status"] == "completed"
            assert recovered_body["dataset_version_id"] == VERSION_ID
            assert recovered_body["requested_by"] == USER_ID
            assert recovered_body["created_at"] is not None
            assert recovered_body["started_at"] is not None
            assert recovered_body["completed_at"] is not None
            assert recovered_body["error_message"] is None
            assert recovered_body["result"]["prediction_value"] == 15.0
            assert recovered_body["result"]["metrics"] == {
                "mae": 15.0,
                "rmse": 15.0,
            }

            # Verificar aislamiento real por organización sobre scientific_jobs en disco
            # (USER_ID es miembro activo de OTHER_ORGANIZATION_ID, por lo que el 404 proviene de scientific_jobs)
            forbidden_response = restarted_api_client.get(
                f"/api/v1/executions/{job_id}",
                headers={
                    "Authorization": AUTH_HEADERS["Authorization"],
                    "X-Organization-ID": OTHER_ORGANIZATION_ID,
                },
            )
            assert forbidden_response.status_code == 404
    finally:
        first_app.dependency_overrides.clear()
        restarted_app.dependency_overrides.clear()

class _FileSystemBucket:
    """Bucket de Storage simulado que escribe archivos reales en disco."""

    def __init__(self, root: Path):
        self.root = root

    def upload(self, path: str, data: bytes, _file_options: dict[str, str]):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"path": path}

    def remove(self, paths: list[str]):
        for path in paths:
            (self.root / path).unlink(missing_ok=True)
        return {"removed": paths}

    def download(self, path: str) -> bytes:
        return (self.root / path).read_bytes()

    def create_signed_url(self, path: str, expires_in: int):
        if not (self.root / path).is_file():
            raise FileNotFoundError(path)
        return {"signedURL": f"https://storage.test/sign/{path}?exp={expires_in}"}


class _FileSystemStorage:
    def __init__(self, root: Path):
        self.root = root

    def from_(self, bucket: str) -> _FileSystemBucket:
        return _FileSystemBucket(self.root / bucket)


class _PersistentArtifactClient(PersistentSqliteClient):
    """SQLite en disco más Storage simulado sobre el sistema de archivos."""

    def __init__(self, db_path: Path, storage_root: Path):
        super().__init__(db_path)
        self.storage = _FileSystemStorage(storage_root)


def test_model_artifact_file_and_access_persist_across_api_restart(
    tmp_path, monkeypatch
):
    """Tras reiniciar la API, el archivo y su acceso autorizado siguen vigentes (S2-185)."""
    db_path = tmp_path / "scientific_persistent.db"
    storage_root = tmp_path / "storage"
    _init_persistent_sqlite_db(db_path)

    job_id = str(uuid.uuid4())
    artifact_bytes = b"\x80\x04modelo-entrenado\x00"
    expected_checksum = hashlib.sha256(artifact_bytes).hexdigest()
    expected_path = f"models/{job_id}/model.pkl"
    expected_reference = {
        "job_id": job_id,
        "bucket": "model_artifacts",
        "storage_path": expected_path,
        "checksum": expected_checksum,
        "size_bytes": len(artifact_bytes),
    }

    first_app = create_app()
    restarted_app = create_app()

    try:
        # 1. Primera instancia: trabajo completado y artefacto guardado en disco
        first_client = _PersistentArtifactClient(db_path, storage_root)
        first_client.table("scientific_jobs").insert(
            {
                "id": job_id,
                "job_type": "training",
                "config": {"dataset_id": DATASET_ID, "version_id": VERSION_ID},
                "status": "completed",
                "organization_id": ORGANIZATION_ID,
                "requested_by": USER_ID,
            }
        ).execute()
        reference = save_model_artifact(first_client, job_id, artifact_bytes)
        assert reference.storage_path == expected_path
        assert reference.checksum == expected_checksum

        # 2. Reinicio: clientes nuevos sobre los mismos archivos de disco
        first_app.dependency_overrides.clear()
        restarted_client = _PersistentArtifactClient(db_path, storage_root)
        monkeypatch.setattr(controller_execution, "supabase", restarted_client)
        monkeypatch.setattr(service_execution, "supabase", restarted_client)
        restarted_app.dependency_overrides[require_authenticated_user] = (
            fake_authenticated_user
        )

        # 3. El archivo en sí persiste, íntegro, y coincide con el checksum guardado
        persisted = restarted_client.storage.from_("model_artifacts").download(
            expected_path
        )
        assert persisted == artifact_bytes
        assert hashlib.sha256(persisted).hexdigest() == expected_checksum

        with TestClient(restarted_app) as api_client:
            # 4. La referencia al artefacto sigue en el resultado del trabajo
            status_response = api_client.get(
                f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS
            )
            assert status_response.status_code == 200
            assert status_response.json()["result"]["model_artifact"] == (
                expected_reference
            )

            # 5. Acceso autorizado: enlace temporal al archivo privado
            access_response = api_client.get(
                f"/api/v1/executions/{job_id}/artifact", headers=AUTH_HEADERS
            )
            assert access_response.status_code == 200
            access_body = access_response.json()
            assert expected_path in access_body["download_url"]
            assert access_body["checksum"] == expected_checksum
            assert access_body["expires_in"] == 60

            # 6. Otra organización (el usuario es miembro de ambas) no accede
            foreign_headers = {
                "Authorization": AUTH_HEADERS["Authorization"],
                "X-Organization-ID": OTHER_ORGANIZATION_ID,
            }
            foreign_artifact = api_client.get(
                f"/api/v1/executions/{job_id}/artifact", headers=foreign_headers
            )
            assert foreign_artifact.status_code == 404
            assert "storage.test" not in foreign_artifact.text
            assert expected_path not in foreign_artifact.text

            foreign_status = api_client.get(
                f"/api/v1/executions/{job_id}", headers=foreign_headers
            )
            assert foreign_status.status_code == 404

            # 7. Sin autenticación no hay acceso
            anonymous = api_client.get(
                f"/api/v1/executions/{job_id}/artifact",
                headers={"X-Organization-ID": ORGANIZATION_ID},
            )
            assert anonymous.status_code == 401
    finally:
        first_app.dependency_overrides.clear()
        restarted_app.dependency_overrides.clear()
             
def test_estimation_job_resolves_training_and_dataset_origin(fake_database):
    training_job_id = "aaaaaaaa-1111-4111-8111-111111111111"
    fake_database.rows.append(
        {
            "id": training_job_id,
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "completed",
            "config": {"dataset_id": DATASET_ID, "version_id": VERSION_ID},
            "result": {
                "model": "baseline",
                "model_version_id": MODEL_VERSION_ID,
            },
            "dataset_version_id": VERSION_ID,
            "model_version_id": MODEL_VERSION_ID,
        }
    )

    post_response = client.post(
        "/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {
                "model_id": MODEL_VERSION_ID,
                "scene_id": SCENE_ID,
                "training_job_id": training_job_id,
            },
        },
        headers=HEADERS,
    )
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    status_response = client.get(
        f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS
    )
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "completed"
    assert body["result"]["training_job_id"] == training_job_id
    assert body["result"]["dataset_id"] == DATASET_ID
    assert body["result"]["dataset_version_id"] == VERSION_ID
    assert body["result"]["model_version_id"] == MODEL_VERSION_ID


def test_estimation_job_fails_when_training_origin_is_missing(fake_database):
    missing_training_id = "bbbbbbbb-2222-4222-8222-222222222222"
    post_response = client.post(
        "/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {
                "model_id": MODEL_VERSION_ID,
                "scene_id": SCENE_ID,
                "training_job_id": missing_training_id,
            },
        },
        headers=HEADERS,
    )
    assert post_response.status_code == 202
    job_id = post_response.json()["job_id"]

    status_response = client.get(
        f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS
    )
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == (
        "No se encontró el trabajo de entrenamiento de origen del modelo."
    )


@pytest.mark.parametrize(
    ("origin_status", "origin_organization_id", "origin_config", "origin_version_id"),
    [
        ("failed", ORGANIZATION_ID, {"dataset_id": DATASET_ID}, VERSION_ID),
        ("completed", OTHER_ORGANIZATION_ID, {"dataset_id": DATASET_ID}, VERSION_ID),
        ("completed", ORGANIZATION_ID, {"dataset_id": DATASET_ID}, None),
    ],
)
def test_estimation_rejects_unverified_training_origins(
    fake_database,
    origin_status,
    origin_organization_id,
    origin_config,
    origin_version_id,
):
    training_job_id = "aaaaaaaa-3333-4333-8333-333333333333"
    fake_database.rows.append(
        {
            "id": training_job_id,
            "organization_id": origin_organization_id,
            "job_type": "training",
            "status": origin_status,
            "config": origin_config,
            "result": {},
            "dataset_version_id": origin_version_id,
        }
    )

    response = client.post(
        "/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {
                "model_id": MODEL_VERSION_ID,
                "scene_id": SCENE_ID,
                "training_job_id": training_job_id,
            },
        },
        headers=HEADERS,
    )
    job_id = response.json()["job_id"]

    status_response = client.get(
        f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS
    )

    assert response.status_code == 202
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "failed"
    if origin_status != "completed":
        assert "aún no está completado" in body["error_message"]
    elif origin_organization_id != ORGANIZATION_ID:
        assert "No se encontró el trabajo" in body["error_message"]
    else:
        assert "dataset y su versión" in body["error_message"]


def test_estimation_finds_training_by_id_when_model_version_id_is_null(
    fake_database,
):
    fake_database.rows.append(
        {
            "id": "bbbbbbbb-1111-4111-8111-111111111111",
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "failed",
            "config": {"dataset_id": DATASET_ID, "version_id": VERSION_ID},
            "result": {},
            "dataset_version_id": VERSION_ID,
            "model_version_id": MODEL_VERSION_ID,
        }
    )
    fake_database.rows.append(
        {
            "id": MODEL_VERSION_ID,
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "completed",
            "config": {"dataset_id": DATASET_ID, "version_id": VERSION_ID},
            "result": {"model": "baseline"},
            "dataset_version_id": VERSION_ID,
            "model_version_id": None,
        }
    )

    response = client.post(
        "/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {"model_id": MODEL_VERSION_ID, "scene_id": SCENE_ID},
        },
        headers=HEADERS,
    )
    job_id = response.json()["job_id"]
    status_response = client.get(
        f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS
    )

    assert response.status_code == 202
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["result"]["training_job_id"] == MODEL_VERSION_ID
    assert status_response.json()["result"]["dataset_id"] == DATASET_ID
    assert status_response.json()["result"]["dataset_version_id"] == VERSION_ID


def test_estimation_rejects_mismatched_training_and_model_versions(fake_database):
    training_job_id = "aaaaaaaa-4444-4444-8444-444444444444"
    fake_database.rows.append(
        {
            "id": training_job_id,
            "organization_id": ORGANIZATION_ID,
            "job_type": "training",
            "status": "completed",
            "config": {"dataset_id": DATASET_ID, "version_id": VERSION_ID},
            "result": {"model_version_id": MODEL_VERSION_ID},
            "dataset_version_id": VERSION_ID,
            "model_version_id": MODEL_VERSION_ID,
        }
    )

    response = client.post(
        "/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {
                "model_id": MODEL_VERSION_ID,
                "scene_id": SCENE_ID,
                "training_job_id": training_job_id,
                "model_version_id": OTHER_MODEL_VERSION_ID,
            },
        },
        headers=HEADERS,
    )
    job_id = response.json()["job_id"]
    status_response = client.get(
        f"/api/v1/executions/{job_id}", headers=AUTH_HEADERS
    )

    assert response.status_code == 202
    assert status_response.json()["status"] == "failed"
    assert (
        status_response.json()["error_message"]
        == "El entrenamiento de origen no corresponde al modelo indicado."
    )


def test_estimation_does_not_persist_unverified_dataset_version(
    fake_database, monkeypatch
):
    async def skip_worker(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "apps.scientific.app.domains.execution.service_execution.process_scientific_job",
        skip_worker,
    )
    response = client.post(
        "/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {
                "model_id": MODEL_VERSION_ID,
                "scene_id": SCENE_ID,
                "dataset_version_id": VERSION_ID,
            },
        },
        headers=HEADERS,
    )

    assert response.status_code == 202
    assert "dataset_version_id" not in fake_database.rows[0]


def test_pilot_report_schema_validates_complete_and_rejects_missing_provenance():
    """Valida un informe piloto completo y rechaza la omisión de provenance (S3-09)."""
    from pydantic import ValidationError

    from apps.scientific.app.domains.execution.schemas_execution import PilotReport

    valid_payload = {
        "method": {
            "model": "baseline",
            "strategy": "mean_clorofila_a",
            "target_variable": "clorofila_a",
            "split_strategy": "sequential",
            "split_ratio": 0.8,
            "configuration": {"algorithm": "baseline"},
            "code_version": "dev",
            "environment": "test",
        },
        "results": {
            "prediction_value": 15.0,
            "predictions": [15.0],
            "metrics": {"mae": 15.0, "rmse": 15.0},
            "train_sample_count": 2,
            "validation_sample_count": 1,
        },
        "limitations": [
            "Modelo baseline de referencia; no incorpora variables espectrales ni espaciales."
        ],
        "provenance": {
            "dataset_id": DATASET_ID,
            "dataset_version_id": VERSION_ID,
            "model_version_id": None,
            "manifest": {
                "manifest_checksum": "a" * 64,
                "storage_path": f"datasets/{DATASET_ID}/v1/manifest.json",
                "sources": ["sentinel-2:S2A_MSIL2A_20261120"],
            },
        },
    }

    report = PilotReport.model_validate(valid_payload)
    assert report.method.model == "baseline"
    assert report.results.metrics.mae == 15.0
    assert len(report.limitations) == 1
    assert report.provenance.dataset_version_id == VERSION_ID
    assert report.provenance.manifest.manifest_checksum == "a" * 64

    invalid_payload = {
        key: value for key, value in valid_payload.items() if key != "provenance"
    }
    with pytest.raises(ValidationError) as exc_info:
        PilotReport.model_validate(invalid_payload)

    assert any(err["loc"] == ("provenance",) for err in exc_info.value.errors())


def test_training_execution_persists_validated_pilot_report(fake_database, monkeypatch):
    """La ejecución de entrenamiento real genera pilot_report con los 4 bloques mínimos (S3-09)."""
    from apps.scientific.app.domains.execution.schemas_execution import PilotReport

    csv_data = b"clorofila_a\n10.0\n20.0\n30.0\n"
    checksum = hashlib.sha256(csv_data).hexdigest()
    monkeypatch.setattr(
        service_execution,
        "fetch_training_file",
        lambda _version_id, _organization_id, _user_id: (csv_data, checksum),
    )

    create_response = client.post(
        "/api/v1/executions/",
        json=training_payload(),
        headers=HEADERS,
    )
    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]

    status_response = client.get(
        f"/api/v1/executions/{job_id}",
        headers=AUTH_HEADERS,
    )
    assert status_response.status_code == 200
    pilot_report_data = status_response.json()["result"]["pilot_report"]
    validated = PilotReport.model_validate(pilot_report_data)

    assert validated.method.strategy == "mean_clorofila_a"
    assert validated.results.prediction_value == 15.0
    assert len(validated.limitations) >= 1
    assert validated.provenance.dataset_version_id == VERSION_ID
    assert validated.provenance.manifest.manifest_checksum == checksum
