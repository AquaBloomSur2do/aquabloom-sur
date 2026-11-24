import asyncio
import hashlib
import os
import uuid
from datetime import UTC, datetime
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
from apps.scientific.app.domains.execution.domain_execution import (
    MAX_ERROR_MESSAGE_LENGTH,
    JobLimitExceededError,
    calculate_baseline,
    parse_training_csv,
    resolve_job_timeout,
)
from apps.scientific.app.domains.execution.model_execution import (
    fetch_training_file,
)
from apps.scientific.app.domains.execution.service_execution import (
    process_scientific_job,
)
from apps.scientific.app.main import app

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
                str(row.get(column)) == value
                for column, value in self.filters.items()
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
    monkeypatch.setitem(
        app.dependency_overrides,
        require_authenticated_user,
        fake_authenticated_user,
    )
    return database


def estimation_payload(model_id="model_v1", scene_id="scene_001"):
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

    response = client.get(
        f"/api/v1/executions/{job_id}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": OTHER_ORGANIZATION_ID,
        },
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró el trabajo."


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
        json=estimation_payload(model_id="model_v2", scene_id="scene_002"),
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
    payload = estimation_payload(scene_id="scene_003")
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
    payload = estimation_payload(scene_id="scene_fail")

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

    payload = estimation_payload(scene_id="scene_timeout")
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
    config = {"model_id": "model_v1", "scene_id": "scene_001"}
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
        json=estimation_payload(scene_id="scene_fail"),
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
    assert (
        response.json()["message"] == "La versión no pertenece al dataset indicado."
    )
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


def test_model_fetches_training_file_for_version():
    mock_client = MagicMock()
    expected_checksum = "a" * 64
    csv_content = b"clorofila_a\n10.0\n"
    (
        mock_client.schema.return_value.table.return_value.select.return_value.eq.return_value
        .limit.return_value.execute.return_value.data
    ) = [
        {
            "storage_path": f"versions/{VERSION_ID}/training.csv",
            "checksum": expected_checksum,
        }
    ]
    mock_client.storage.from_.return_value.download.return_value = csv_content

    assert fetch_training_file(mock_client, VERSION_ID) == (
        csv_content,
        expected_checksum,
    )
    mock_client.schema.return_value.table.return_value.select.return_value.eq.assert_called_once_with(
        "version_id", VERSION_ID
    )
    mock_client.storage.from_.assert_called_once_with("training_files")
    mock_client.storage.from_.return_value.download.assert_called_once_with(
        f"versions/{VERSION_ID}/training.csv"
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
    fetch_file.assert_called_once_with(fake_database, VERSION_ID)


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
    