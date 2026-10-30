from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import verify_supabase_jwt
from app.datasets import APIError, validate_state_transition
from app.main import app
from app.schemas import DatasetVersionStateUpdate, VersionState

client = TestClient(app)

# ==========================================
# Pruebas S2-134: Ciclo de vida y estados
# ==========================================

def test_schema_accepts_all_five_states():
    for state in ["DRAFT", "IN_REVIEW", "APPROVED", "PUBLISHED", "ARCHIVED"]:
        model = DatasetVersionStateUpdate(state=VersionState(state))
        assert model.state.value == state

def test_schema_rejects_invalid_state():
    with pytest.raises(ValidationError):
        DatasetVersionStateUpdate(state="INVALID_STATE")

def test_valid_version_state_transitions():
    validate_state_transition(VersionState.DRAFT, VersionState.IN_REVIEW)
    validate_state_transition(VersionState.IN_REVIEW, VersionState.APPROVED)
    validate_state_transition(VersionState.APPROVED, VersionState.PUBLISHED)
    validate_state_transition(VersionState.DRAFT, VersionState.ARCHIVED)

def test_invalid_version_state_transitions_raise_400():
    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.DRAFT, VersionState.PUBLISHED)
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.PUBLISHED, VersionState.DRAFT)
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.ARCHIVED, VersionState.DRAFT)
    assert exc_info.value.status_code == 400


# ==========================================
# Pruebas S2-105 / S2-134: Endpoints y Supabase Mock
# ==========================================

class FakeQuery:
    def __init__(self, database, schema_name, table_name):
        self.database = database
        self.schema_name = schema_name
        self.table_name = table_name
        self.filters = {}
        self.in_filters = {}
        self.inserted = None
        self.updated = None
        self._limit = None
        self.is_count = False

    def select(self, *_args, **kwargs):
        if kwargs.get("count") == "exact":
            self.is_count = True
        return self

    def eq(self, field, value):
        self.filters[field] = str(value)
        return self

    def in_(self, field, values):
        self.in_filters[field] = [str(v) for v in values]
        return self

    def range(self, start, end):
        return self

    def limit(self, count):
        self._limit = count
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, row):
        self.inserted = row
        return self

    def update(self, payload):
        self.updated = payload
        return self

    def execute(self):
        if self.inserted is not None and self.database.database_error is not None:
            raise self.database.database_error

        if self.schema_name != "dataset":
            rows = self.database.organization_memberships
            if self.filters.get("organization_id"):
                rows = [
                    row for row in rows
                    if str(row["organization_id"]) == self.filters["organization_id"]
                ]
            if self.filters.get("user_id"):
                rows = [
                    row for row in rows if str(row["user_id"]) == self.filters["user_id"]
                ]
            if self.filters.get("status"):
                rows = [row for row in rows if str(row["status"]) == self.filters["status"]]
            return SimpleNamespace(data=rows)

        rows = self.database.dataset_rows.get(self.table_name, [])
        if self.inserted is not None:
            if isinstance(self.inserted, list):
                self.database.dataset_rows.setdefault(self.table_name, []).extend(self.inserted)
                return SimpleNamespace(data=self.inserted)
            row = {
                **self.inserted,
                "id": "decision-new",
                "decided_at": "2026-10-27T00:00:00+00:00",
            }
            self.database.dataset_rows.setdefault(self.table_name, []).append(row)
            return SimpleNamespace(data=[row])

        if self.updated is not None:
            updated_rows = []
            for row in rows:
                match = all(str(row.get(f)) == v for f, v in self.filters.items())
                if match:
                    row.update(self.updated)
                    updated_rows.append(row.copy())
            return SimpleNamespace(data=updated_rows)

        for field, value in self.filters.items():
            rows = [row for row in rows if str(row.get(field)) == value]
        for field, values in self.in_filters.items():
            rows = [row for row in rows if str(row.get(field)) in values]

        if self._limit is not None:
            rows = rows[:self._limit]

        count = len(rows) if self.is_count else None
        return SimpleNamespace(data=rows, count=count)

class FakeSchema:
    def __init__(self, database, schema_name):
        self.database = database
        self.schema_name = schema_name

    def table(self, table_name):
        return FakeQuery(self.database, self.schema_name, table_name)

class FakeSupabase:
    def __init__(self, user_id, organization_role):
        self.dataset_id = "11111111-1111-1111-1111-111111111111"
        self.organization_id = "22222222-2222-2222-2222-222222222222"
        self.version_id = "33333333-3333-3333-3333-333333333333"
        self.membership_id = str(uuid4())
        self.user_id = str(user_id)
        self.database_error = None
        self.organization_memberships = [
            {
                "user_id": self.user_id,
                "organization_id": self.organization_id,
                "role": organization_role,
                "status": "active",
            }
        ]
        self.dataset_rows = {
            "datasets": [
                {
                    "id": self.dataset_id,
                    "organization_id": self.organization_id,
                    "name": "Dataset piloto",
                    "description": None,
                    "created_at": "2026-10-27T00:00:00+00:00",
                }
            ],
            "versions": [
                {
                    "id": self.version_id,
                    "dataset_id": self.dataset_id,
                    "version_number": 1,
                    "state": "DRAFT",
                    "status": "DRAFT",
                    "created_at": "2026-10-27T00:00:00+00:00",
                }
            ],
            "memberships": [
                {
                    "id": self.membership_id,
                    "version_id": self.version_id,
                    "scene_provider": "sentinel",
                    "scene_external_id": "scene-pilot",
                    "added_at": "2026-10-27T00:00:00+00:00",
                }
            ],
            "decisions": [],
        }

    def table(self, table_name):
        return FakeQuery(self, "public", table_name)

    def schema(self, name):
        return FakeSchema(self, name)

def setup_request(monkeypatch, role):
    user_id = uuid4()
    database = FakeSupabase(user_id, role)
    monkeypatch.setattr("app.datasets.supabase", database)
    app.dependency_overrides[verify_supabase_jwt] = lambda: {"sub": str(user_id)}
    return database


# --- S2-105: List datasets ---

def test_list_review_datasets_returns_memberships_for_active_organization(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    try:
        response = client.get("/api/v1/datasets/review")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    dataset = data[0]
    assert dataset["id"] == database.dataset_id
    assert dataset["versions"][0]["memberships"][0]["scene_external_id"] == "scene-pilot"
    assert dataset["versions"][0]["memberships"][0]["decisions"] == []


# --- S2-105: Decisions ---

def test_investigator_cannot_register_a_decision(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    try:
        response = client.post(
            f"/api/v1/datasets/memberships/{database.membership_id}/decisions",
            json={"decision": "accepted", "reason": "Escena válida"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert database.dataset_rows["decisions"] == []

def test_admin_from_another_organization_cannot_register_a_decision(monkeypatch):
    database = setup_request(monkeypatch, "admin")
    database.organization_memberships[0]["organization_id"] = "organization-other"
    try:
        response = client.post(
            f"/api/v1/datasets/memberships/{database.membership_id}/decisions",
            json={"decision": "accepted", "reason": "Escena válida"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert database.dataset_rows["decisions"] == []

def test_decision_requires_a_non_blank_reason(monkeypatch):
    database = setup_request(monkeypatch, "supervisor")
    try:
        response = client.post(
            f"/api/v1/datasets/memberships/{database.membership_id}/decisions",
            json={"decision": "accepted", "reason": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert database.dataset_rows["decisions"] == []

@pytest.mark.parametrize(
    ("decision", "reason"),
    [("rejected", "Nubes densas"), ("accepted", "Escena válida")],
)
def test_supervisor_registers_decision_and_reason(monkeypatch, decision, reason):
    database = setup_request(monkeypatch, "supervisor")
    try:
        response = client.post(
            f"/api/v1/datasets/memberships/{database.membership_id}/decisions",
            json={"decision": decision, "reason": f"  {reason}  "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["decision"] == decision
    assert response.json()["reason"] == reason
    assert response.json()["decided_by"] == database.user_id
    assert response.json()["decided_at"] == "2026-10-27T00:00:00+00:00"
    stored_decision = database.dataset_rows["decisions"][0]
    assert stored_decision["decision"] == decision
    assert stored_decision["reason"] == reason

@pytest.mark.parametrize(
    ("error_code", "expected_status", "postgrest_error"),
    [
        ("23505", 409, False),
        ("23503", 404, False),
        ("XX000", 500, False),
        ("23505", 409, True),
        ("23503", 404, True),
        ("XX000", 500, True),
    ],
)
def test_database_errors_are_mapped_when_registering_decision(
    monkeypatch, error_code, expected_status, postgrest_error
):
    database = setup_request(monkeypatch, "supervisor")
    database_error = (
        APIError({"code": error_code, "message": "database error"})
        if postgrest_error
        else Exception("database error")
    )
    if not postgrest_error:
        database_error.code = error_code
    database.database_error = database_error

    try:
        response = client.post(
            f"/api/v1/datasets/memberships/{database.membership_id}/decisions",
            json={"decision": "accepted", "reason": "Escena válida"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected_status
    assert database.dataset_rows["decisions"] == []


# --- S2-134: Actualización de Estados ---

def test_update_version_state_persists_in_database(monkeypatch):
    database = setup_request(monkeypatch, "admin")
    try:
        response = client.patch(
            f"/api/v1/datasets/versions/{database.version_id}/state",
            json={"state": "IN_REVIEW"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert database.dataset_rows["versions"][0]["state"] == "IN_REVIEW"
    assert database.dataset_rows["versions"][0]["status"] == "IN_REVIEW"

def test_update_version_state_returns_404_for_missing_version(monkeypatch):
    setup_request(monkeypatch, "admin")
    try:
        response = client.patch(
            f"/api/v1/datasets/versions/{uuid4()}/state",
            json={"state": "IN_REVIEW"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404

def test_update_version_state_returns_403_when_unauthorized(monkeypatch):
    database = setup_request(monkeypatch, "member")
    try:
        response = client.patch(
            f"/api/v1/datasets/versions/{database.version_id}/state",
            json={"state": "IN_REVIEW"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403

def test_update_version_state_returns_400_for_unknown_current_state(monkeypatch):
    database = setup_request(monkeypatch, "admin")
    database.dataset_rows["versions"][0]["state"] = "CORRUPTED_STATE"
    try:
        response = client.patch(
            f"/api/v1/datasets/versions/{database.version_id}/state",
            json={"state": "IN_REVIEW"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400

    