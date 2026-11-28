from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.domains.reports import controller_reports
from apps.api.app.domains.reports.controller_reports import router as reports_router

app = FastAPI()
app.include_router(reports_router)
client = TestClient(app)


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.filters = {}
        self.in_filters = {}
        self.insert_payload = None
        self.update_payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters[field] = str(value)
        return self

    def in_(self, field, values):
        self.in_filters[field] = {str(value) for value in values}
        return self

    def limit(self, _count):
        return self

    def insert(self, payload):
        self.insert_payload = payload
        return self

    def update(self, payload):
        self.update_payload = payload
        return self

    def execute(self):
        rows = self.database.tables.setdefault(self.table_name, [])
        if self.insert_payload is not None:
            row = {
                **self.insert_payload,
                "id": str(uuid4()),
                "created_at": "2026-11-27T12:00:00+00:00",
                "updated_at": "2026-11-27T12:00:00+00:00",
                "resolution_reason": None,
                "resolved_by": None,
                "resolved_at": None,
            }
            rows.append(row)
            return SimpleNamespace(data=[row.copy()])

        matches = [
            row
            for row in rows
            if all(str(row.get(field)) == value for field, value in self.filters.items())
            and all(
                str(row.get(field)) in values
                for field, values in self.in_filters.items()
            )
        ]
        if self.update_payload is not None:
            for row in matches:
                row.update(self.update_payload)
            return SimpleNamespace(data=[row.copy() for row in matches])
        return SimpleNamespace(data=[row.copy() for row in matches])


class FakeSupabase:
    def __init__(self, lake_id, station_id):
        self.tables = {
            "lakes": [{"id": str(lake_id)}],
            "stations": [{"id": str(station_id)}],
            "resource_reports": [],
            "memberships": [],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


@pytest.fixture
def reports_context(monkeypatch):
    reporter_id = uuid4()
    moderator_id = uuid4()
    lake_id = uuid4()
    station_id = uuid4()
    database = FakeSupabase(lake_id, station_id)
    auth_payload = {
        "sub": str(reporter_id),
        "user_metadata": {"role": "investigador"},
    }

    monkeypatch.setattr(controller_reports, "supabase", database)
    app.dependency_overrides[verify_supabase_jwt] = lambda: auth_payload
    try:
        yield {
            "database": database,
            "reporter_id": reporter_id,
            "moderator_id": moderator_id,
            "lake_id": lake_id,
            "station_id": station_id,
            "auth_payload": auth_payload,
        }
    finally:
        app.dependency_overrides.clear()


def test_authenticated_report_is_persisted_and_moderator_resolution_is_traceable(
    reports_context,
):
    context = reports_context

    created_response = client.post(
        "/api/v1/reports",
        json={
            "resource_type": "lake",
            "resource_id": str(context["lake_id"]),
            "reason": "Información de calidad incorrecta",
            "details": "El dato de turbidez requiere revisión.",
        },
    )

    assert created_response.status_code == 201
    created_report = created_response.json()
    assert created_report["status"] == "open"
    assert created_report["reported_by"] == str(context["reporter_id"])
    assert created_report["reason"] == "Información de calidad incorrecta"
    assert created_report["details"] == "El dato de turbidez requiere revisión."
    assert context["database"].tables["resource_reports"][0]["id"] == created_report[
        "id"
    ]

    context["auth_payload"].update(
        {
            "sub": str(context["moderator_id"]),
            "user_metadata": {"role": "supervisor"},
        }
    )
    context["database"].tables["memberships"].append(
        {
            "user_id": str(context["moderator_id"]),
            "organization_id": str(uuid4()),
            "role": "supervisor",
            "status": "active",
        }
    )
    resolution_reason = "Reporte verificado y corregido."
    resolved_response = client.patch(
        f"/api/v1/reports/{created_report['id']}/resolve",
        json={"resolution_reason": resolution_reason},
    )

    assert resolved_response.status_code == 200
    consulted_response = client.get(f"/api/v1/reports/{created_report['id']}")

    assert consulted_response.status_code == 200
    resolved_report = consulted_response.json()
    assert resolved_report["reported_by"] == str(context["reporter_id"])
    assert resolved_report["status"] == "resolved"
    assert resolved_report["resolution_reason"] == resolution_reason
    assert resolved_report["resolved_by"] == str(context["moderator_id"])


def test_reporter_cannot_resolve_their_own_report(reports_context):
    context = reports_context
    context["database"].tables["memberships"].append(
        {
            "user_id": str(context["reporter_id"]),
            "organization_id": str(uuid4()),
            "role": "investigador",
            "status": "active",
        }
    )
    created_response = client.post(
        "/api/v1/reports",
        json={
            "resource_type": "station",
            "resource_id": str(context["station_id"]),
            "reason": "Estación requiere revisión",
        },
    )
    assert created_response.status_code == 201
    report_id = created_response.json()["id"]
    context["auth_payload"]["user_metadata"]["role"] = "supervisor"

    response = client.patch(
        f"/api/v1/reports/{report_id}/resolve",
        json={"resolution_reason": "No corresponde."},
    )

    assert response.status_code == 403
    stored_report = context["database"].tables["resource_reports"][0]
    assert stored_report["status"] == "open"
    assert stored_report["resolved_by"] is None
    assert stored_report["resolution_reason"] is None
