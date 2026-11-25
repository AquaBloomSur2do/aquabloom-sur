import math
import os
import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-secret-token")

from apps.api.app.core.auth import verify_supabase_jwt as api_verify_jwt
from apps.api.app.domains.dataset import controller_dataset
from apps.api.app.main import app as api_app
from apps.satellite.app.core.auth import (
    verify_supabase_jwt as satellite_verify_jwt,
)
from apps.satellite.app.domains.scenes import controller_scenes
from apps.scientific.app.core.config import settings as scientific_settings
from apps.scientific.app.core.dependencies import require_authenticated_user
from apps.scientific.app.domains.execution import controller_execution
from apps.scientific.app.domains.prediction import controller_prediction
from apps.scientific.app.main import app as scientific_app

api_client = TestClient(api_app)
scientific_client = TestClient(scientific_app)

USER_ID = "11111111-1111-4111-8111-111111111111"
ORGANIZATION_ID = "22222222-2222-4222-8222-222222222222"
LAKE_ID = "33333333-3333-4333-8333-333333333333"
SCENE_ID = "44444444-4444-4444-8444-444444444444"
DATASET_ID = "55555555-5555-4555-8555-555555555555"
VERSION_ID = "66666666-6666-4666-8666-666666666666"
MANIFEST_ID = "77777777-7777-4777-8777-777777777777"
MODEL_VERSION_ID = "88888888-8888-4888-8888-888888888888"
JOB_ID = "99999999-9999-4999-8999-999999999999"

INTERNAL_HEADERS = {"X-Internal-Token": "test-secret-token"}
ORG_HEADERS = {
    "Authorization": "Bearer test-user-token",
    "X-Organization-ID": ORGANIZATION_ID,
}
EXECUTION_HEADERS = {**ORG_HEADERS, **INTERNAL_HEADERS}


def _fake_user() -> dict[str, str]:
    return {"sub": USER_ID}


def _resolve_ref(openapi_doc: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/"), f"Referencia OpenAPI no soportada: {ref}"
    node: Any = openapi_doc
    for part in ref[2:].split("/"):
        node = node[part]
    assert isinstance(node, dict), f"Referencia inválida: {ref}"
    return node


def _validate_format(value: str, fmt: str, path: str) -> None:
    if fmt == "uuid":
        try:
            uuid.UUID(value)
        except ValueError as exc:
            raise AssertionError(f"{path}: '{value}' no es un UUID válido") from exc
    elif fmt == "date":
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise AssertionError(
                f"{path}: '{value}' no es una fecha ISO válida"
            ) from exc
    elif fmt == "date-time":
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise AssertionError(
                f"{path}: '{value}' no es un datetime ISO válido"
            ) from exc


def _validate_type(value: Any, expected_type: str, path: str) -> None:
    if expected_type == "null":
        assert value is None, f"{path}: se esperaba null, se recibió {type(value).__name__}"
    elif expected_type == "boolean":
        assert isinstance(value, bool), f"{path}: se esperaba boolean"
    elif expected_type == "integer":
        assert isinstance(value, int) and not isinstance(value, bool), (
            f"{path}: se esperaba integer, se recibió {value!r}"
        )
    elif expected_type == "number":
        assert (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        ), f"{path}: se esperaba number finito, se recibió {value!r}"
    elif expected_type == "string":
        assert isinstance(value, str), f"{path}: se esperaba string, se recibió {value!r}"
    elif expected_type == "array":
        assert isinstance(value, list), f"{path}: se esperaba array, se recibió {value!r}"
    elif expected_type == "object":
        assert isinstance(value, dict), f"{path}: se esperaba object, se recibió {value!r}"


def validate_against_schema(
    value: Any,
    schema: dict[str, Any],
    openapi_doc: dict[str, Any],
    path: str = "$",
) -> None:
    """Valida recursivamente una respuesta JSON real contra un esquema OpenAPI 3.x."""
    if "$ref" in schema:
        schema = _resolve_ref(openapi_doc, schema["$ref"])

    if "allOf" in schema:
        for subschema in schema["allOf"]:
            validate_against_schema(value, subschema, openapi_doc, path)
        return

    for composite_key in ("anyOf", "oneOf"):
        if composite_key in schema:
            errors: list[str] = []
            for subschema in schema[composite_key]:
                try:
                    validate_against_schema(value, subschema, openapi_doc, path)
                    return
                except AssertionError as exc:
                    errors.append(str(exc))
            raise AssertionError(
                f"{path}: el valor {value!r} no cumplió {composite_key}: {errors}"
            )

    if value is None and schema.get("nullable"):
        return

    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        type_errors: list[str] = []
        for candidate in expected_type:
            try:
                _validate_type(value, candidate, path)
                break
            except AssertionError as exc:
                type_errors.append(str(exc))
        else:
            raise AssertionError(
                f"{path}: tipo inválido para {value!r}: {type_errors}"
            )
    elif isinstance(expected_type, str):
        _validate_type(value, expected_type, path)

    if "enum" in schema:
        assert value in schema["enum"], (
            f"{path}: {value!r} no pertenece al enum {schema['enum']}"
        )

    if "const" in schema:
        assert value == schema["const"], (
            f"{path}: se esperaba const {schema['const']!r}, se recibió {value!r}"
        )

    if isinstance(value, str):
        if "minLength" in schema:
            assert len(value) >= schema["minLength"], f"{path}: longitud menor a minLength"
        if "format" in schema:
            _validate_format(value, schema["format"], path)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema:
            assert value >= schema["minimum"], f"{path}: {value} < minimum {schema['minimum']}"
        if "maximum" in schema:
            assert value <= schema["maximum"], f"{path}: {value} > maximum {schema['maximum']}"

    if isinstance(value, list):
        if "minItems" in schema:
            assert len(value) >= schema["minItems"], f"{path}: menos elementos que minItems"
        if "items" in schema:
            for index, item in enumerate(value):
                validate_against_schema(
                    item, schema["items"], openapi_doc, f"{path}[{index}]"
                )

    if isinstance(value, dict):
        for req_field in schema.get("required", []):
            assert req_field in value, f"{path}: falta campo obligatorio '{req_field}'"

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)

        for key, prop_value in value.items():
            prop_path = f"{path}.{key}"
            if key in properties:
                validate_against_schema(
                    prop_value, properties[key], openapi_doc, prop_path
                )
            elif additional is False:
                raise AssertionError(f"{prop_path}: campo adicional no permitido por OpenAPI")
            elif isinstance(additional, dict):
                validate_against_schema(
                    prop_value, additional, openapi_doc, prop_path
                )


def assert_response_matches_openapi(
    test_client: TestClient,
    path_template: str,
    method: str,
    status_code: int,
    response_json: Any,
) -> None:
    openapi_response = test_client.get("/openapi.json")
    assert openapi_response.status_code == 200
    openapi_doc = openapi_response.json()

    assert path_template in openapi_doc["paths"], (
        f"Ruta {path_template} no declarada en OpenAPI"
    )
    operation = openapi_doc["paths"][path_template][method.lower()]
    responses = operation["responses"]
    assert str(status_code) in responses, (
        f"Código {status_code} no declarado en OpenAPI para {method.upper()} {path_template}"
    )

    schema = responses[str(status_code)]["content"]["application/json"]["schema"]
    validate_against_schema(response_json, schema, openapi_doc)


@pytest.fixture(autouse=True)
def override_auth_and_internal_token(monkeypatch):
    monkeypatch.setattr(
        scientific_settings,
        "internal_service_token",
        SecretStr("test-secret-token"),
    )
    monkeypatch.setitem(api_app.dependency_overrides, api_verify_jwt, _fake_user)
    monkeypatch.setitem(api_app.dependency_overrides, satellite_verify_jwt, _fake_user)
    monkeypatch.setitem(
        api_app.dependency_overrides, require_authenticated_user, _fake_user
    )
    monkeypatch.setitem(
        scientific_app.dependency_overrides, require_authenticated_user, _fake_user
    )


def test_scene_endpoint_response_matches_openapi(monkeypatch):
    """Verifica respuesta real de listado de escenas contra OpenAPI (S2-180)."""
    monkeypatch.setattr(controller_scenes, "supabase", object())
    monkeypatch.setattr(
        controller_scenes,
        "list_scenes_service",
        lambda *_args, **_kwargs: {
            "items": [
                {
                    "id": SCENE_ID,
                    "lake_id": LAKE_ID,
                    "scene_identifier": "S2A_MSIL2A_20261120_VILLARRICA",
                    "acquisition_date": "2026-11-20",
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
            "page": 1,
            "page_size": 10,
            "total": 1,
        },
    )

    response = api_client.get(
        "/api/v1/scenes",
        params={
            "lake_id": LAKE_ID,
            "start_date": "2026-11-01",
            "end_date": "2026-11-30",
            "page": 1,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    assert_response_matches_openapi(
        api_client, "/api/v1/scenes", "get", 200, response.json()
    )


def test_dataset_training_manifest_response_matches_openapi(monkeypatch):
    """Verifica respuesta real de metadatos de dataset contra OpenAPI (S2-180)."""
    fake_client = SimpleNamespace(schema=lambda _name: object())
    monkeypatch.setattr(controller_dataset, "supabase", fake_client)
    monkeypatch.setattr(
        controller_dataset,
        "validate_training_file_access",
        lambda *_args, **_kwargs: {
            "id": MANIFEST_ID,
            "variables": ["clorofila_a", "NDCI"],
            "checksum": "a" * 64,
        },
    )

    response = api_client.get(
        f"/api/v1/datasets/versions/{VERSION_ID}/training-file"
    )

    assert response.status_code == 200
    assert_response_matches_openapi(
        api_client,
        "/api/v1/datasets/versions/{version_id}/training-file",
        "get",
        200,
        response.json(),
    )


def test_execution_job_create_and_status_responses_match_openapi(monkeypatch):
    """Verifica respuestas reales de creación y consulta de trabajo contra OpenAPI (S2-180)."""
    monkeypatch.setattr(controller_execution, "supabase", object())
    monkeypatch.setattr(
        controller_execution,
        "create_execution_job_service",
        lambda *_args, **_kwargs: {
            "job_id": JOB_ID,
            "status": "queued",
            "status_url": f"/api/v1/executions/{JOB_ID}",
        },
    )
    monkeypatch.setattr(
        controller_execution,
        "get_job_status_service",
        lambda *_args, **_kwargs: {
            "job_id": JOB_ID,
            "job_type": "training",
            "status": "completed",
            "config": {
                "dataset_id": DATASET_ID,
                "version_id": VERSION_ID,
                "epochs": 50,
                "learning_rate": 0.01,
            },
            "result": {
                "model": "baseline",
                "baseline": {
                    "strategy": "mean_clorofila_a",
                    "target_variable": "clorofila_a",
                    "prediction_value": 15.0,
                    "train_sample_count": 2,
                    "validation_sample_count": 1,
                },
                "prediction_value": 15.0,
                "predictions": [15.0],
                "metrics": {"mae": 15.0, "rmse": 15.0},
                "version": VERSION_ID,
                "dataset_version_id": VERSION_ID,
                "model_version_id": None,
                "status": "completed",
                "warnings": [],
            },
            "dataset_version_id": VERSION_ID,
            "model_version_id": None,
            "requested_by": USER_ID,
            "error_message": None,
            "created_at": datetime.now(UTC).isoformat(),
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )

    create_response = api_client.post(
        "/api/v1/executions/",
        json={
            "job_type": "training",
            "config": {
                "dataset_id": DATASET_ID,
                "version_id": VERSION_ID,
                "epochs": 50,
                "learning_rate": 0.01,
            },
        },
        headers=EXECUTION_HEADERS,
    )
    assert create_response.status_code == 202
    assert_response_matches_openapi(
        api_client, "/api/v1/executions/", "post", 202, create_response.json()
    )

    status_response = api_client.get(
        f"/api/v1/executions/{JOB_ID}",
        headers=ORG_HEADERS,
    )
    assert status_response.status_code == 200
    assert_response_matches_openapi(
        api_client,
        "/api/v1/executions/{job_id}",
        "get",
        200,
        status_response.json(),
    )


def test_estimation_and_prediction_responses_match_openapi(monkeypatch):
    """Verifica respuestas reales de estimación y predicción contra OpenAPI (S2-180)."""
    monkeypatch.setattr(controller_execution, "supabase", object())
    monkeypatch.setattr(
        controller_execution,
        "create_execution_job_service",
        lambda *_args, **_kwargs: {
            "job_id": JOB_ID,
            "status": "queued",
            "status_url": f"/api/v1/executions/{JOB_ID}",
        },
    )

    estimation_response = scientific_client.post(
        "/api/v1/executions/",
        json={
            "job_type": "estimation",
            "config": {"model_id": MODEL_VERSION_ID, "scene_id": SCENE_ID},
        },
        headers=EXECUTION_HEADERS,
    )
    assert estimation_response.status_code == 202
    assert_response_matches_openapi(
        scientific_client,
        "/api/v1/executions/",
        "post",
        202,
        estimation_response.json(),
    )

    monkeypatch.setattr(controller_prediction, "supabase", object())
    monkeypatch.setattr(
        controller_prediction,
        "create_prediction_service",
        lambda *_args, **_kwargs: {
            "id": str(uuid.uuid4()),
            "model_version_id": MODEL_VERSION_ID,
            "scene_id": SCENE_ID,
            "result": {"chlorophyll_a": 12.5, "unit": "ug/L"},
            "rules": [{"rule_id": "cloud-mask", "version": "1.0", "parameters": {}}],
            "created_at": datetime.now(UTC).isoformat(),
        },
    )

    prediction_response = scientific_client.post(
        "/api/v1/predictions/",
        json={
            "model_version_id": MODEL_VERSION_ID,
            "scene_id": SCENE_ID,
            "result": {"chlorophyll_a": 12.5, "unit": "ug/L"},
            "rules": [{"rule_id": "cloud-mask", "version": "1.0"}],
        },
        headers=INTERNAL_HEADERS,
    )
    assert prediction_response.status_code == 201
    assert_response_matches_openapi(
        scientific_client,
        "/api/v1/predictions/",
        "post",
        201,
        prediction_response.json(),
    )


