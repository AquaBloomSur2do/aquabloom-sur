"""HTTP traceability contract for pilot estimation jobs.

S3-59 report persistence/query integration is not present in main. The existing
pilot_report is generated for training results; pilot_report_ref below is only
a report reference shape, not a persisted report. Its estimation_job_id is
resolved through the real GET endpoint against an isolated test database.
"""

import copy
import os
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Header, HTTPException, status
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.scientific.app.core.dependencies import require_authenticated_user
from apps.scientific.app.domains.execution import (
    controller_execution,
    service_execution,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    TraceabilityEvidence,
)
from apps.scientific.app.main import app

client = TestClient(app)

JOB_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
UNKNOWN_JOB_ID = "abababab-abab-4bab-8bab-abababababab"
USER_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"
ORGANIZATION_ID = "99999999-9999-4999-8999-999999999999"
OTHER_ORGANIZATION_ID = "88888888-8888-4888-8888-888888888888"
NO_MEMBERSHIP_ORGANIZATION_ID = "77777777-7777-4777-8777-777777777777"
EVIDENCE = {
    "job_id": JOB_ID,
    "scene_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "dataset_version_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "model_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "processing_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
}
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
    def __init__(self, row):
        self.row = row
        self.filters = {}

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters[column] = str(value)
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        matches = self.row is not None and all(
            str(self.row.get(column)) == value for column, value in self.filters.items()
        )
        return SimpleNamespace(data=[self.row] if matches else [])


class FakeDatabase:
    def __init__(self, row):
        self.row = row
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
        self.queried_tables = []

    def table(self, table_name):
        assert table_name == "scientific_jobs"
        self.queried_tables.append(table_name)
        return FakeQuery(self.row)


def estimation_job_row(result=None):
    return {
        "id": JOB_ID,
        "organization_id": ORGANIZATION_ID,
        "job_type": "estimation",
        "status": "completed",
        "config": {},
        "result": (
            {"processed_pixels": 102400, "traceability_evidence": EVIDENCE}
            if result is None
            else result
        ),
        "created_at": "2026-11-17T00:00:00Z",
    }


@pytest.fixture
def execution_api_client(monkeypatch):
    database = FakeDatabase(estimation_job_row())
    monkeypatch.setattr(controller_execution, "supabase", database)
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
    monkeypatch.setitem(
        app.dependency_overrides,
        require_authenticated_user,
        fake_authenticated_user,
    )
    return client, database


def test_pilot_report_reference_resolves_complete_evidence_over_http(
    execution_api_client,
):
    api_client, database = execution_api_client
    row_before_request = copy.deepcopy(database.row)
    pilot_report_ref = {"estimation_job_id": JOB_ID}

    response = api_client.get(
        f"/api/v1/executions/{pilot_report_ref['estimation_job_id']}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    evidence = data["traceability_evidence"]
    assert data["job_id"] == JOB_ID
    assert evidence["job_id"] == JOB_ID
    assert evidence["dataset_version_id"] == EVIDENCE["dataset_version_id"]
    assert evidence["scene_id"] == EVIDENCE["scene_id"]
    assert evidence["model_id"] == EVIDENCE["model_id"]
    assert UUID(evidence["processing_id"]) == UUID(EVIDENCE["processing_id"])
    assert database.row == row_before_request
    assert database.queried_tables == ["scientific_jobs"]


def test_get_estimation_traceability_requires_authentication(
    execution_api_client,
):
    api_client, _database = execution_api_client

    response = api_client.get(
        f"/api/v1/executions/{JOB_ID}",
        headers={"X-Organization-ID": ORGANIZATION_ID},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("requested_job_id", "requested_organization_id"),
    [
        (UNKNOWN_JOB_ID, ORGANIZATION_ID),
        (JOB_ID, OTHER_ORGANIZATION_ID),
        (JOB_ID, NO_MEMBERSHIP_ORGANIZATION_ID),
    ],
)
def test_get_estimation_traceability_hides_missing_or_foreign_evidence(
    execution_api_client, requested_job_id, requested_organization_id
):
    api_client, _database = execution_api_client

    response = api_client.get(
        f"/api/v1/executions/{requested_job_id}",
        headers={
            "Authorization": AUTH_HEADERS["Authorization"],
            "X-Organization-ID": requested_organization_id,
        },
    )

    assert response.status_code == 404
    for evidence_id in EVIDENCE.values():
        assert evidence_id not in response.text


@pytest.mark.parametrize("missing_link", ["model_id", "scene_id"])
def test_traceability_evidence_rejects_missing_required_links(missing_link):
    incomplete_evidence = dict(EVIDENCE)
    del incomplete_evidence[missing_link]

    with pytest.raises(ValidationError):
        TraceabilityEvidence.model_validate(incomplete_evidence)


@pytest.mark.parametrize("legacy_result", [None, {"processed_pixels": 102400}])
def test_get_historical_estimation_without_evidence_returns_none(
    execution_api_client, legacy_result
):
    api_client, database = execution_api_client
    database.row["result"] = legacy_result

    response = api_client.get(
        f"/api/v1/executions/{JOB_ID}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["traceability_evidence"] is None
