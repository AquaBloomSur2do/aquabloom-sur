import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-secret-token")

from apps.api.app.core.auth import optional_verify_supabase_jwt
from apps.api.app.domains.catalog import controller_catalog
from apps.api.app.gateway import executions_bridge
from apps.api.app.main import app as api_app
from apps.api.tests.test_openapi_contracts import (
    assert_response_matches_openapi,
    validate_against_schema,
)
from apps.satellite.app.core.auth import (
    verify_supabase_jwt as satellite_verify_jwt,
)
from apps.satellite.app.domains.scenes import controller_scenes
from apps.scientific.app.core.dependencies import require_authenticated_user
from apps.scientific.app.domains.execution import controller_execution
from apps.scientific.app.main import app as scientific_app

api_client = TestClient(api_app)

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts" / "openapi"

USER_ID = "11111111-1111-4111-8111-111111111111"
ORGANIZATION_ID = "22222222-2222-4222-8222-222222222222"
LAKE_ID = "33333333-3333-4333-8333-333333333333"
STATION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SCENE_ID = "44444444-4444-4444-8444-444444444444"
DATASET_ID = "55555555-5555-4555-8555-555555555555"
VERSION_ID = "66666666-6666-4666-8666-666666666666"
MODEL_VERSION_ID = "88888888-8888-4888-8888-888888888888"
JOB_ID = "99999999-9999-4999-8999-999999999999"

ORG_HEADERS = {
    "Authorization": "Bearer test-user-token",
    "X-Organization-ID": ORGANIZATION_ID,
}


@pytest.fixture(autouse=True)
def reset_api_overrides():
    previous_overrides = dict(api_app.dependency_overrides)
    api_app.dependency_overrides.clear()
    try:
        yield
    finally:
        api_app.dependency_overrides.clear()
        api_app.dependency_overrides.update(previous_overrides)


def _load_contract(filename: str) -> dict:
    path = CONTRACTS_DIR / filename
    assert path.is_file(), f"No existe el contrato candidato: {path}"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"Contrato inválido: {path}"
    return document


@pytest.fixture(scope="module")
def contract_documents() -> dict[str, dict]:
    return {
        "scientific": _load_contract("scientific.yaml"),
        "satellite": _load_contract("satellite.yaml"),
    }


def test_candidate_contracts_declare_critical_operations(contract_documents):
    scientific = contract_documents["scientific"]
    satellite = contract_documents["satellite"]

    assert str(scientific["openapi"]).startswith("3.")
    assert str(satellite["openapi"]).startswith("3.")

    job_status_operation = scientific["paths"]["/executions/{job_id}"]["get"]
    assert {"200", "401", "404"} <= set(job_status_operation["responses"])

    scientific_schemas = scientific["components"]["schemas"]
    for schema_name in (
        "JobStatus",
        "TrainingResult",
        "TrainingMetrics",
        "BaselineInfo",
    ):
        assert schema_name in scientific_schemas

    assert scientific_schemas["JobStatus"]["required"] == [
        "job_id",
        "job_type",
        "status",
        "config",
        "created_at",
    ]
    assert scientific_schemas["JobStatus"]["properties"]["job_type"]["enum"] == [
        "training",
        "modeling",
        "estimation",
    ]
    assert scientific_schemas["JobStatus"]["properties"]["status"]["enum"] == [
        "queued",
        "running",
        "completed",
        "failed",
    ]

    scenes_operations = satellite["paths"]["/scenes"]
    assert {"get", "post"} <= set(scenes_operations)
    assert {"200", "400"} <= set(scenes_operations["get"]["responses"])

    satellite_schemas = satellite["components"]["schemas"]
    for schema_name in (
        "SceneList",
        "SceneDetail",
        "SceneRegistration",
        "ErrorResponse",
    ):
        assert schema_name in satellite_schemas
    assert set(satellite_schemas["ErrorResponse"]["required"]) == {
        "type",
        "code",
        "message",
        "correlation_id",
    }


def test_gateway_openapi_covers_catalog_estimation_and_jobs():
    spec = api_app.openapi()
    paths = spec["paths"]
    expected_operations = {
        "/api/v1/lakes": {"get", "post"},
        "/api/v1/lakes/{lake_id}": {"get", "patch", "delete"},
        "/api/v1/lakes/{lake_id}/stations": {"get", "post"},
        "/api/v1/scenes": {"get"},
        "/api/v1/executions/jobs": {"post"},
        "/api/v1/executions/": {"post"},
        "/api/v1/executions/{job_id}": {"get"},
    }
    for path, methods in expected_operations.items():
        assert path in paths, f"Ruta {path} no declarada en el Gateway"
        assert methods <= set(paths[path]), (
            f"Métodos faltantes en {path}: {methods - set(paths[path])}"
        )

    schemas = spec["components"]["schemas"]
    for schema_name in (
        "PaginatedLakes",
        "LakeDetail",
        "StationOut",
        "PaginatedScenes",
        "JobResponse",
        "JobStatus",
    ):
        assert schema_name in schemas

    assert paths["/api/v1/lakes"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"] == "#/components/schemas/PaginatedLakes"
    assert paths["/api/v1/executions/jobs"]["post"]["responses"]["202"]["content"][
        "application/json"
    ]["schema"]["$ref"] == "#/components/schemas/JobResponse"
    assert paths["/api/v1/executions/{job_id}"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"] == "#/components/schemas/JobStatus"


def test_scientific_candidate_schema_matches_live_service(contract_documents):
    candidate = contract_documents["scientific"]["components"]["schemas"]
    live = scientific_app.openapi()["components"]["schemas"]

    candidate_job = candidate["JobStatus"]
    live_job = live["JobStatus"]
    assert set(candidate_job["required"]) <= set(live_job["required"])
    for field in candidate_job["properties"]:
        assert field in live_job["properties"]

    assert (
        candidate_job["properties"]["job_type"]["enum"]
        == live["ScientificJobType"]["enum"]
    )
    assert (
        candidate_job["properties"]["status"]["enum"]
        == live["ScientificJobStatusEnum"]["enum"]
    )

    for schema_name in ("TrainingResult", "TrainingMetrics", "BaselineInfo"):
        for field in candidate[schema_name]["properties"]:
            assert field in live[schema_name]["properties"], (
                f"El campo {field} de {schema_name} no existe en el contrato servido"
            )


def test_catalog_responses_match_gateway_openapi(monkeypatch):
    now = datetime.now(UTC).isoformat()
    lake_summary = {
        "id": LAKE_ID,
        "name": "Lago Panguipulli",
        "region": "Los Ríos",
        "description": "Lago de origen glaciar",
        "status": "active",
        "stations_count": 1,
    }
    lake_detail = {
        **lake_summary,
        "geom": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-72.1, -39.6],
                    [-72.2, -39.6],
                    [-72.2, -39.7],
                    [-72.1, -39.7],
                    [-72.1, -39.6],
                ]
            ],
        },
        "created_at": now,
        "updated_at": now,
    }
    station = {
        "id": STATION_ID,
        "lake_id": LAKE_ID,
        "code": "EST-01",
        "name": "Estación Centro",
        "point": {"type": "Point", "coordinates": [-72.5, -38.7]},
        "description": "Estación de monitoreo",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }

    monkeypatch.setattr(controller_catalog, "supabase", object())
    monkeypatch.setattr(
        controller_catalog,
        "get_lakes_repository",
        lambda *_args, **_kwargs: {
            "items": [lake_summary],
            "page": 1,
            "page_size": 10,
            "total": 1,
        },
    )
    monkeypatch.setattr(
        controller_catalog,
        "get_lake_by_id",
        lambda *_args, **_kwargs: lake_detail,
    )
    monkeypatch.setattr(
        controller_catalog,
        "get_lake_stations_from_db",
        lambda *_args, **_kwargs: [station],
    )

    list_response = api_client.get("/api/v1/lakes")
    assert list_response.status_code == 200
    assert_response_matches_openapi(
        api_client, "/api/v1/lakes", "get", 200, list_response.json()
    )

    detail_response = api_client.get(f"/api/v1/lakes/{LAKE_ID}")
    assert detail_response.status_code == 200
    assert_response_matches_openapi(
        api_client,
        "/api/v1/lakes/{lake_id}",
        "get",
        200,
        detail_response.json(),
    )

    stations_response = api_client.get(f"/api/v1/lakes/{LAKE_ID}/stations")
    assert stations_response.status_code == 200
    assert_response_matches_openapi(
        api_client,
        "/api/v1/lakes/{lake_id}/stations",
        "get",
        200,
        stations_response.json(),
    )


def test_scene_response_matches_gateway_openapi(monkeypatch):
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
    monkeypatch.setitem(
        api_app.dependency_overrides,
        satellite_verify_jwt,
        lambda: {"sub": USER_ID},
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


def test_gateway_job_creation_and_estimation_status_match_contracts(
    monkeypatch, contract_documents
):
    monkeypatch.setattr(executions_bridge, "supabase", object())
    monkeypatch.setitem(
        api_app.dependency_overrides,
        require_authenticated_user,
        lambda: {"sub": USER_ID},
    )
    monkeypatch.setattr(
        executions_bridge,
        "create_execution_job_service",
        lambda *_args, **_kwargs: {
            "job_id": JOB_ID,
            "status": "queued",
            "status_url": f"/api/v1/executions/{JOB_ID}",
        },
    )

    create_response = api_client.post(
        "/api/v1/executions/jobs",
        json={
            "job_type": "ESTIMATION",
            "config": {"model_id": MODEL_VERSION_ID, "scene_id": SCENE_ID},
        },
        headers=ORG_HEADERS,
    )

    assert create_response.status_code == 202
    assert_response_matches_openapi(
        api_client,
        "/api/v1/executions/jobs",
        "post",
        202,
        create_response.json(),
    )

    now = datetime.now(UTC).isoformat()
    estimation_status = {
        "job_id": JOB_ID,
        "job_type": "estimation",
        "status": "completed",
        "config": {"model_id": MODEL_VERSION_ID, "scene_id": SCENE_ID},
        "result": {
            "model_id": MODEL_VERSION_ID,
            "model_name": "random_forest",
            "unit": "ug/L",
            "status": "completed",
            "warnings": [],
            "predictions": [
                {
                    "point_id": "est-01",
                    "station_name": "Estación Centro",
                    "latitude": -38.7359,
                    "longitude": -72.5904,
                    "predicted_value": 14.8,
                    "unit": "ug/L",
                }
            ],
        },
        "dataset_version_id": VERSION_ID,
        "model_version_id": MODEL_VERSION_ID,
        "scene_id": SCENE_ID,
        "requested_by": USER_ID,
        "error_message": None,
        "created_at": now,
        "started_at": now,
        "completed_at": now,
        "updated_at": now,
    }
    monkeypatch.setattr(controller_execution, "supabase", object())
    monkeypatch.setattr(
        controller_execution,
        "get_job_status_service",
        lambda *_args, **_kwargs: estimation_status,
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
    validate_against_schema(
        status_response.json(),
        contract_documents["scientific"]["components"]["schemas"]["JobStatus"],
        contract_documents["scientific"],
    )


def test_job_error_codes_are_declared_in_contracts(contract_documents):
    candidate_get = contract_documents["scientific"]["paths"][
        "/executions/{job_id}"
    ]["get"]
    assert {"200", "401", "404"} <= set(candidate_get["responses"])

    api_spec = api_app.openapi()
    scientific_spec = scientific_app.openapi()
    for spec in (api_spec, scientific_spec):
        operation = spec["paths"]["/api/v1/executions/{job_id}"]["get"]
        assert {"200", "401", "404", "503"} <= set(operation["responses"])

    gateway_jobs = api_spec["paths"]["/api/v1/executions/jobs"]["post"]
    assert {"202", "401", "404", "409", "422", "503"} <= set(
        gateway_jobs["responses"]
    )

    catalog_get = api_spec["paths"]["/api/v1/lakes"]["get"]
    assert {"200", "401", "403", "404", "409", "422"} <= set(
        catalog_get["responses"]
    )


def test_runtime_error_codes_use_safe_envelope_and_correlation_id(monkeypatch):
    def unauthorized():
        raise HTTPException(status_code=401, detail="Token inválido")

    monkeypatch.setitem(
        api_app.dependency_overrides, optional_verify_supabase_jwt, unauthorized
    )
    response = api_client.get("/api/v1/lakes?status=inactive")
    assert response.status_code == 401
    assert response.headers["x-correlation-id"]
    assert {"error", "message"} <= set(response.json())

    monkeypatch.setitem(
        api_app.dependency_overrides,
        optional_verify_supabase_jwt,
        lambda: {"sub": USER_ID, "user_metadata": {}},
    )
    response = api_client.get("/api/v1/lakes?status=inactive")
    assert response.status_code == 403
    assert response.headers["x-correlation-id"]
    assert {"error", "message"} <= set(response.json())

    def missing_lake(*_args, **_kwargs):
        raise LookupError("El lago no existe.")

    monkeypatch.setattr(controller_catalog, "supabase", object())
    monkeypatch.setattr(controller_catalog, "get_lake_by_id", missing_lake)
    response = api_client.get(f"/api/v1/lakes/{LAKE_ID}")
    assert response.status_code == 404
    assert response.headers["x-correlation-id"]
    assert {"error", "message"} <= set(response.json())

    response = api_client.get("/api/v1/lakes?page=no-es-entero")
    assert response.status_code == 422
    assert response.headers["x-correlation-id"]
    assert {"error", "message", "details"} <= set(response.json())

    monkeypatch.setitem(
        api_app.dependency_overrides,
        require_authenticated_user,
        lambda: {"sub": USER_ID},
    )
    monkeypatch.setattr(controller_execution, "supabase", None)
    response = api_client.get(
        f"/api/v1/executions/{JOB_ID}",
        headers=ORG_HEADERS,
    )
    assert response.status_code == 503
    assert response.headers["x-correlation-id"]
    assert {"error", "message"} <= set(response.json())

    monkeypatch.setattr(executions_bridge, "supabase", object())
    monkeypatch.setattr(
        executions_bridge,
        "get_dataset_version_for_training",
        lambda *_args, **_kwargs: None,
    )
    response = api_client.post(
        "/api/v1/executions/jobs",
        json={"job_type": "TRAINING", "config": {"version_id": VERSION_ID}},
        headers=ORG_HEADERS,
    )
    assert response.status_code == 404
    assert response.headers["x-correlation-id"]
    assert {"error", "message"} <= set(response.json())

    monkeypatch.setattr(
        executions_bridge,
        "get_dataset_version_for_training",
        lambda *_args, **_kwargs: {
            "dataset_id": DATASET_ID,
            "state": "DRAFT",
        },
    )
    response = api_client.post(
        "/api/v1/executions/jobs",
        json={"job_type": "TRAINING", "config": {"version_id": VERSION_ID}},
        headers=ORG_HEADERS,
    )
    assert response.status_code == 409
    assert response.headers["x-correlation-id"]
    assert {"error", "message"} <= set(response.json())
