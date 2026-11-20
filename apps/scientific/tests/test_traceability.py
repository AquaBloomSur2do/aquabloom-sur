import os
from types import SimpleNamespace
from uuid import UUID

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")


JOB_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
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

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def limit(self, _limit):
        return self

    def execute(self):
        return SimpleNamespace(data=[self.row])


class FakeDatabase:
    def __init__(self, row):
        self.row = row

    def table(self, _table_name):
        return FakeQuery(self.row)


def test_job_status_exposes_validated_traceability_evidence():
    from apps.scientific.app.domains.execution.schemas_execution import (
        JobStatus,
        TraceabilityEvidence,
    )
    from apps.scientific.app.domains.execution.service_execution import (
        get_job_status_service,
    )

    row = {
        "id": JOB_ID,
        "job_type": "estimation",
        "status": "completed",
        "config": {},
        "result": {"accuracy": 0.98, "traceability_evidence": EVIDENCE},
        "created_at": "2026-11-17T00:00:00Z",
    }

    status = get_job_status_service(FakeDatabase(row), UUID(JOB_ID))
    response = JobStatus.model_validate(status)

    assert response.traceability_evidence == TraceabilityEvidence.model_validate(
        EVIDENCE
    )
