import os
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")


JOB_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
UNKNOWN_JOB_ID = "abababab-abab-4bab-8bab-abababababab"
USER_ID = "ffffffff-ffff-4fff-8fff-ffffffffffff"
ORGANIZATION_ID = "99999999-9999-4999-8999-999999999999"
OTHER_ORGANIZATION_ID = "88888888-8888-4888-8888-888888888888"
EVIDENCE = {
    "job_id": JOB_ID,
    "scene_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "dataset_version_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "model_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "processing_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
}


class FakeQuery:
    def __init__(self, row):
        self.row = row
        self.filters = {}

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters[column] = str(value)
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        matches = all(
            str(self.row.get(column)) == value for column, value in self.filters.items()
        )
        return SimpleNamespace(data=[self.row] if matches else [])


class FakeDatabase:
    def __init__(self, row):
        self.row = row

    def table(self, _table_name):
        return FakeQuery(self.row)


def test_estimation_job_id_resolves_four_pilot_evidence_links(monkeypatch):
    from apps.scientific.app.domains.execution import service_execution
    from apps.scientific.app.domains.execution.schemas_execution import (
        JobStatus,
        TraceabilityEvidence,
    )

    monkeypatch.setattr(
        service_execution,
        "has_active_organization_membership",
        lambda _user_id, _organization_id: True,
    )
    row = {
        "id": JOB_ID,
        "organization_id": ORGANIZATION_ID,
        "job_type": "estimation",
        "status": "completed",
        "config": {},
        "result": {"accuracy": 0.98, "traceability_evidence": EVIDENCE},
        "created_at": "2026-11-17T00:00:00Z",
    }

    status = service_execution.get_job_status_service(
        FakeDatabase(row), UUID(JOB_ID), UUID(USER_ID), UUID(ORGANIZATION_ID)
    )
    response = JobStatus.model_validate(status)

    assert response.id == UUID(JOB_ID)
    assert response.traceability_evidence == TraceabilityEvidence.model_validate(
        EVIDENCE
    )
    assert response.traceability_evidence.job_id == response.id
    assert response.traceability_evidence.dataset_version_id == UUID(
        EVIDENCE["dataset_version_id"]
    )
    assert response.traceability_evidence.scene_id == UUID(EVIDENCE["scene_id"])
    assert response.traceability_evidence.model_id == EVIDENCE["model_id"]
    assert "job_id" not in row
    assert "traceability_evidence" not in row


@pytest.mark.parametrize(
    ("requested_job_id", "requested_organization_id"),
    [
        (UNKNOWN_JOB_ID, ORGANIZATION_ID),
        (JOB_ID, OTHER_ORGANIZATION_ID),
    ],
)
def test_estimation_traceability_returns_404_for_missing_or_foreign_job(
    monkeypatch, requested_job_id, requested_organization_id
):
    from apps.scientific.app.domains.execution import service_execution

    monkeypatch.setattr(
        service_execution,
        "has_active_organization_membership",
        lambda _user_id, _organization_id: True,
    )
    row = {
        "id": JOB_ID,
        "organization_id": ORGANIZATION_ID,
        "job_type": "estimation",
        "status": "completed",
        "config": {},
        "result": {"traceability_evidence": EVIDENCE},
        "created_at": "2026-11-17T00:00:00Z",
    }

    with pytest.raises(HTTPException) as error:
        service_execution.get_job_status_service(
            FakeDatabase(row),
            UUID(requested_job_id),
            UUID(USER_ID),
            UUID(requested_organization_id),
        )

    assert error.value.status_code == 404
