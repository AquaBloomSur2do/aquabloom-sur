import os
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.domains.library import controller_library
from apps.api.app.main import app

client = TestClient(app)

AUTHOR_ID = "11111111-1111-4111-8111-111111111111"
VALID_VERSION_ID = "66666666-6666-4666-8666-666666666666"
MISSING_VERSION_ID = "99999999-9999-4999-8999-999999999999"


class FakeQuery:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows
        self._filters: dict[str, Any] = {}
        self._insert_payload: dict[str, Any] | None = None

    def select(self, _columns: str):
        return self

    def eq(self, column: str, value: Any):
        self._filters[column] = value
        return self

    def limit(self, _count: int):
        return self

    def insert(self, payload: dict[str, Any]):
        self._insert_payload = dict(payload)
        return self

    def execute(self):
        if self._insert_payload is not None:
            created = {
                "id": str(uuid4()),
                "notes": None,
                **self._insert_payload,
                "created_at": datetime.now(UTC).isoformat(),
            }
            self._rows.append(created)
            return SimpleNamespace(data=[created])

        matched = [
            row
            for row in self._rows
            if all(str(row.get(k)) == str(v) for k, v in self._filters.items())
        ]
        return SimpleNamespace(data=matched)


class FakeSchemaClient:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]):
        self._tables = tables

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self._tables.setdefault(table_name, []))


class FakeSupabaseClient:
    def __init__(self, existing_version_ids: list[str]):
        self.schemas: dict[str, dict[str, list[dict[str, Any]]]] = {
            "public": {"resource_review_requests": []},
            "dataset": {
                "versions": [{"id": version_id} for version_id in existing_version_ids]
            },
        }

    def schema(self, schema_name: str) -> FakeSchemaClient:
        return FakeSchemaClient(self.schemas.setdefault(schema_name, {}))

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self.schemas["public"].setdefault(table_name, []))


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeSupabaseClient(existing_version_ids=[VALID_VERSION_ID])
    monkeypatch.setattr(controller_library, "supabase", db)
    app.dependency_overrides[verify_supabase_jwt] = lambda: {"sub": AUTHOR_ID}
    yield db
    app.dependency_overrides.pop(verify_supabase_jwt, None)


def test_creates_review_request_with_version_authenticated_author_date_and_initial_status(
    fake_db,
):
    response = client.post(
        "/api/v1/library/review-requests",
        json={
            "version_id": VALID_VERSION_ID,
            "notes": "Lista para revisión técnica.",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version_id"] == VALID_VERSION_ID
    assert body["author_id"] == AUTHOR_ID
    assert body["status"] == "submitted"
    assert body["notes"] == "Lista para revisión técnica."
    parsed_date = datetime.fromisoformat(body["created_at"])
    assert parsed_date.tzinfo is not None

    persisted = fake_db.schemas["public"]["resource_review_requests"]
    assert len(persisted) == 1
    assert persisted[0]["version_id"] == VALID_VERSION_ID
    assert persisted[0]["author_id"] == AUTHOR_ID
    assert persisted[0]["status"] == "submitted"


def test_rejects_review_request_when_version_does_not_exist(fake_db):
    response = client.post(
        "/api/v1/library/review-requests",
        json={"version_id": MISSING_VERSION_ID},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert fake_db.schemas["public"]["resource_review_requests"] == []


def test_rejects_client_supplied_author_status_or_created_at(fake_db):
    response = client.post(
        "/api/v1/library/review-requests",
        json={
            "version_id": VALID_VERSION_ID,
            "author_id": "22222222-2222-4222-8222-222222222222",
            "status": "approved",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 422
    assert fake_db.schemas["public"]["resource_review_requests"] == []
