import os
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError
from pydantic import SecretStr

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.scientific.app.core.config import settings
from apps.scientific.app.core.dependencies import require_authenticated_user
from apps.scientific.app.domains.prediction import (
    controller_prediction,
    service_prediction,
)
from apps.scientific.app.main import app

client = TestClient(app)

HEADERS = {"X-Internal-Token": "test-secret-token"}
USER_ID = "11111111-1111-4111-8111-111111111111"
UNAUTHORIZED_USER_ID = "22222222-2222-4222-8222-222222222222"
ORGANIZATION_ID = "33333333-3333-4333-8333-333333333333"
OTHER_ORGANIZATION_ID = "44444444-4444-4444-8444-444444444444"
LAKE_ID = "55555555-5555-4555-8555-555555555555"
DATASET_VERSION_ID = "66666666-6666-4666-8666-666666666666"
MODEL_VERSION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SCENE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

AUTH_HEADERS = {
    "Authorization": "Bearer test-user-token",
    "X-Organization-ID": ORGANIZATION_ID,
}


def fake_authenticated_user(
    authorization: str | None = Header(default=None),
) -> dict:
    if authorization == "Bearer test-user-token":
        return {"sub": USER_ID}
    if authorization == "Bearer unauthorized-role-token":
        return {"sub": UNAUTHORIZED_USER_ID}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Usuario no autenticado",
    )


@pytest.fixture(autouse=True)
def internal_service_token_and_auth(monkeypatch):
    monkeypatch.setattr(
        settings,
        "internal_service_token",
        SecretStr("test-secret-token"),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        require_authenticated_user,
        fake_authenticated_user,
    )


class FakePredictionQuery:
    def __init__(self, database, schema_name, table_name):
        self.database = database
        self.schema_name = schema_name
        self.table_name = table_name
        self.filters = {}
        self.insert_payload = None

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

        if self.schema_name == "satellite" and self.table_name == "scenes":
            rows = [
                scene
                for scene in self.database.scenes
                if all(
                    str(scene.get(key)) == str(value)
                    for key, value in self.filters.items()
                )
            ]
            return SimpleNamespace(data=rows)

        if self.schema_name != "scientific" or self.table_name != "predictions":
            raise AssertionError(
                f"Unexpected query: {self.schema_name}.{self.table_name}"
            )

        if self.insert_payload is not None:
            if self.database.fail_on_insert:
                raise APIError({"code": "23503", "message": "foreign key violation"})
            row = {
                **self.insert_payload,
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
            }
            self.database.rows.append(row)
            return SimpleNamespace(data=[row])

        rows = [
            row
            for row in self.database.rows
            if all(
                row.get(key) is not None and str(row.get(key)) == str(value)
                for key, value in self.filters.items()
            )
        ]
        return SimpleNamespace(data=rows)


class FakePredictionDatabase:
    def __init__(self):
        self.rows = []
        self.fail_on_insert = False
        self.memberships = [
            {
                "user_id": USER_ID,
                "organization_id": ORGANIZATION_ID,
                "role": "investigador",
                "status": "active",
                "organization_status": "active",
            },
            {
                "user_id": USER_ID,
                "organization_id": OTHER_ORGANIZATION_ID,
                "role": "auditor",
                "status": "active",
                "organization_status": "active",
            },
            {
                "user_id": UNAUTHORIZED_USER_ID,
                "organization_id": ORGANIZATION_ID,
                "role": "invitado_sin_permisos",
                "status": "active",
                "organization_status": "active",
            },
        ]
        self.scenes = [
            {
                "id": SCENE_ID,
                "lake_id": LAKE_ID,
                "scene_identifier": "S2A_MSIL2A_20261120_VILLARRICA",
                "acquisition_date": "2026-11-20",
                "is_experimental": False,
            }
        ]

    def schema(self, schema_name):
        return SimpleNamespace(
            table=lambda table_name: FakePredictionQuery(self, schema_name, table_name)
        )

    def table(self, table_name):
        return FakePredictionQuery(self, None, table_name)


def prediction_payload():
    return {
        "model_version_id": MODEL_VERSION_ID,
        "scene_id": SCENE_ID,
        "result": {"chlorophyll_a": 12.5, "unit": "ug/L"},
        "rules": [{"rule_id": "cloud-mask", "version": "1.0"}],
    }


def mock_prediction_service_contracts(monkeypatch, database):
    def get_membership(user_id, organization_id):
        for membership in database.memberships:
            if (
                membership["user_id"] == str(user_id)
                and membership["organization_id"] == str(organization_id)
                and membership["status"] == "active"
                and membership["organization_status"] == "active"
            ):
                return {
                    "organization_id": membership["organization_id"],
                    "role": membership["role"],
                    "status": membership["status"],
                }
        return None

    def get_scene(scene_id):
        return next(
            (scene for scene in database.scenes if scene["id"] == str(scene_id)),
            None,
        )

    monkeypatch.setattr(
        service_prediction,
        "get_active_membership_for_organization",
        get_membership,
    )
    monkeypatch.setattr(
        service_prediction,
        "get_scene_metadata_in_db",
        get_scene,
    )


def detailed_prediction_payload():
    return {
        "model_version_id": MODEL_VERSION_ID,
        "scene_id": SCENE_ID,
        "organization_id": ORGANIZATION_ID,
        "result": {
            "variable": "chlorophyll_a",
            "unit": "ug/L",
            "status": "completed",
            "dataset_version_id": DATASET_VERSION_ID,
            "points": [
                {
                    "point_id": "est-01",
                    "latitude": -39.275,
                    "longitude": -72.102,
                    "value": 14.8,
                    "label": "Estación Centro",
                    "quality": "VALID",
                },
                {
                    "point_id": "est-02",
                    "latitude": -39.281,
                    "longitude": -72.115,
                    "value": 18.2,
                    "label": "Estación Norte",
                    "quality": "EXTRAPOLATED",
                },
            ],
            "warnings": ["Punto est-02 excede el rango observado del modelo."],
        },
        "rules": [
            {
                "rule_id": "cloud-mask",
                "version": "1.0",
                "parameters": {"max_cloud_pct": 15},
            }
        ],
    }


# =========================================================
# PRUEBAS S2-172: PERSISTENCIA INMUTABLE DE PREDICCIONES
# =========================================================


def test_create_prediction_appends_each_result(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)
    payload = prediction_payload()

    first = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)
    second = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["created_at"] != "" and second.json()["created_at"] != ""
    assert len(database.rows) == 2
    assert database.rows[0]["result"] == payload["result"]
    assert database.rows[0]["rules"] == [
        {"rule_id": "cloud-mask", "version": "1.0", "parameters": {}}
    ]
    assert database.rows[0]["model_version_id"] == MODEL_VERSION_ID
    assert database.rows[0]["scene_id"] == SCENE_ID


def test_create_prediction_requires_internal_token(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)

    response = client.post("/api/v1/predictions/", json=prediction_payload())

    assert response.status_code == 401
    assert not database.rows


def test_create_prediction_rejects_extra_fields_at_each_level(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    payload = prediction_payload()
    payload["unexpected"] = True
    payload["rules"][0]["unexpected"] = True

    response = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)

    assert response.status_code == 422
    assert not database.rows


def test_create_prediction_returns_not_found_for_missing_scene(monkeypatch):
    database = FakePredictionDatabase()
    database.fail_on_insert = True
    monkeypatch.setattr(controller_prediction, "supabase", database)

    response = client.post(
        "/api/v1/predictions/", json=prediction_payload(), headers=HEADERS
    )

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró la escena especificada."


# =========================================================
# PRUEBAS S2-174: DETALLE DE ESTIMACIÓN Y PERMISOS
# =========================================================


def test_get_prediction_detail_returns_full_contract_with_verified_permissions(
    monkeypatch,
):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)

    created = client.post(
        "/api/v1/predictions/",
        json=detailed_prediction_payload(),
        headers=HEADERS,
    )
    assert created.status_code == 201
    prediction_id = created.json()["id"]

    response = client.get(f"/api/v1/predictions/{prediction_id}", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == prediction_id
    assert data["organization_id"] == ORGANIZATION_ID
    assert data["variable"] == "chlorophyll_a"
    assert data["unit"] == "ug/L"
    assert data["status"] == "completed"
    assert len(data["points"]) == 2
    assert data["points"][0] == {
        "point_id": "est-01",
        "station_id": None,
        "latitude": -39.275,
        "longitude": -72.102,
        "value": 14.8,
        "label": "Estación Centro",
        "quality": "VALID",
    }
    assert data["provenance"]["model_version_id"] == MODEL_VERSION_ID
    assert data["provenance"]["scene_id"] == SCENE_ID
    assert data["provenance"]["lake_id"] == LAKE_ID
    assert data["provenance"]["scene_identifier"] == "S2A_MSIL2A_20261120_VILLARRICA"
    assert data["provenance"]["acquisition_date"] == "2026-11-20"
    assert data["provenance"]["dataset_version_id"] == DATASET_VERSION_ID
    assert data["provenance"]["rules"] == [
        {
            "rule_id": "cloud-mask",
            "version": "1.0",
            "parameters": {"max_cloud_pct": 15},
        }
    ]
    assert data["warnings"] == [
        "Punto est-02 excede el rango observado del modelo."
    ]
    assert data["usage_limits"] == [
        "Una o más estimaciones están fuera del rango observado por el modelo (extrapolación).",
        "No se dispone de incertidumbre calibrada; el resultado no debe interpretarse como un intervalo de confianza.",
    ]


def test_get_prediction_detail_supports_scalar_result_and_flags_experimental_scene(
    monkeypatch,
):
    database = FakePredictionDatabase()
    database.scenes[0]["is_experimental"] = True
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)

    payload = {**prediction_payload(), "organization_id": ORGANIZATION_ID}
    created = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)
    prediction_id = created.json()["id"]

    response = client.get(f"/api/v1/predictions/{prediction_id}", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["variable"] == "chlorophyll_a"
    assert data["unit"] == "ug/L"
    assert data["status"] == "completed"
    assert len(data["points"]) == 1
    assert data["points"][0]["value"] == 12.5
    assert any("experimental" in warning.lower() for warning in data["warnings"])
    assert data["usage_limits"] == [
        "No se dispone de incertidumbre calibrada; el resultado no debe interpretarse como un intervalo de confianza."
    ]


def test_get_prediction_detail_flags_synthetic_data_and_respects_calibrated_uncertainty(
    monkeypatch,
):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)
    payload = {**prediction_payload(), "organization_id": ORGANIZATION_ID}
    payload["result"].update(
        {
            "dataset_is_synthetic": True,
            "uncertainty": {"calibrated": True},
        }
    )

    created = client.post("/api/v1/predictions/", json=payload, headers=HEADERS)
    prediction_id = created.json()["id"]
    response = client.get(
        f"/api/v1/predictions/{prediction_id}", headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    assert response.json()["usage_limits"] == [
        "El resultado utiliza datos sintéticos y no representa mediciones observacionales reales."
    ]


def test_get_prediction_detail_requires_authentication(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)

    response = client.get(
        f"/api/v1/predictions/{uuid.uuid4()}",
        headers={"X-Organization-ID": ORGANIZATION_ID},
    )

    assert response.status_code == 401


def test_get_prediction_detail_rejects_user_without_active_membership(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)

    response = client.get(
        f"/api/v1/predictions/{uuid.uuid4()}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": "99999999-9999-4999-8999-999999999999",
        },
    )

    assert response.status_code == 403
    assert "organización" in response.json()["message"].lower()


def test_get_prediction_detail_rejects_unauthorized_role(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)

    response = client.get(
        f"/api/v1/predictions/{uuid.uuid4()}",
        headers={
            "Authorization": "Bearer unauthorized-role-token",
            "X-Organization-ID": ORGANIZATION_ID,
        },
    )

    assert response.status_code == 403
    assert "permisos insuficientes" in response.json()["message"].lower()


def test_get_prediction_detail_isolates_predictions_by_organization(monkeypatch):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)

    created = client.post(
        "/api/v1/predictions/",
        json=detailed_prediction_payload(),
        headers=HEADERS,
    )
    prediction_id = created.json()["id"]

    other_org_response = client.get(
        f"/api/v1/predictions/{prediction_id}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": OTHER_ORGANIZATION_ID,
        },
    )

    assert other_org_response.status_code == 404
    assert (
        other_org_response.json()["message"]
        == "No se encontró la estimación solicitada."
    )


def test_get_prediction_detail_returns_404_when_prediction_does_not_exist(
    monkeypatch,
):
    database = FakePredictionDatabase()
    monkeypatch.setattr(controller_prediction, "supabase", database)
    mock_prediction_service_contracts(monkeypatch, database)

    response = client.get(f"/api/v1/predictions/{uuid.uuid4()}", headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert response.json()["message"] == "No se encontró la estimación solicitada."
