from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import verify_supabase_jwt
from app.main import app
from dataset.application.schemas import VersionState

client = TestClient(app)


class FakeQuery:
    def __init__(self, database, schema, table):
        self.database = database
        self.schema_name = schema
        self.table_name = table
        self.filters = {}
        self.in_filters = {}
        self.inserted = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters[field] = value
        return self

    def in_(self, field, values):
        self.in_filters[field] = values
        return self

    def limit(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, row):
        self.inserted = row
        return self

    def execute(self):
        if self.schema_name != "dataset":
            rows = self.database.organization_memberships
            if self.filters.get("organization_id"):
                rows = [
                    row
                    for row in rows
                    if row["organization_id"] == self.filters["organization_id"]
                ]
            if self.filters.get("user_id"):
                rows = [
                    row for row in rows if row["user_id"] == self.filters["user_id"]
                ]
            if self.filters.get("status"):
                rows = [row for row in rows if row["status"] == self.filters["status"]]
            return SimpleNamespace(data=rows)

        rows = self.database.dataset_rows.get(self.table_name, [])
        if self.inserted is not None:
            # --- MOCK EXTENDIDO PARA SOPORTAR INSERCIONES DE LISTAS (S2-136) ---
            if isinstance(self.inserted, list):
                new_rows = []
                for item in self.inserted:
                    new_row = {
                        **item,
                        "id": str(uuid4()),
                        "added_at": "2026-10-27T00:00:00+00:00"
                    }
                    self.database.dataset_rows.setdefault(self.table_name, []).append(new_row)
                    new_rows.append(new_row)
                return SimpleNamespace(data=new_rows)
            else:
                row = {
                    **self.inserted,
                    "id": "decision-new",
                    "decided_at": "2026-10-27T00:00:00+00:00",
                }
                self.database.dataset_rows.setdefault(self.table_name, []).append(row)
                return SimpleNamespace(data=[row])

        for field, value in self.filters.items():
            rows = [row for row in rows if row.get(field) == value]
        for field, values in self.in_filters.items():
            rows = [row for row in rows if row.get(field) in values]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, user_id, organization_role):
        self.dataset_id = str(uuid4())
        self.organization_id = str(uuid4())
        self.version_id = str(uuid4())
        self.membership_id = str(uuid4())
        self.user_id = str(user_id)
        
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
                    "status": "DRAFT",
                    "state": "DRAFT",
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

    def schema(self, schema_name):
        return FakeSchema(self, schema_name)

    def table(self, table_name):
        return FakeQuery(self, "public", table_name)


class FakeSchema:
    def __init__(self, database, schema_name):
        self.database = database
        self.schema_name = schema_name

    def table(self, table_name):
        return FakeQuery(self.database, self.schema_name, table_name)


def setup_request(monkeypatch, role):
    user_id = uuid4()
    database = FakeSupabase(user_id, role)
    monkeypatch.setattr("app.datasets.supabase", database)
    app.dependency_overrides[verify_supabase_jwt] = lambda: {"sub": str(user_id)}
    return database


def test_list_review_datasets_returns_memberships_for_active_organization(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    try:
        response = client.get("/api/v1/datasets/review")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    dataset = response.json()[0]
    assert dataset["id"] == database.dataset_id
    assert (
        dataset["versions"][0]["memberships"][0]["scene_external_id"] == "scene-pilot"
    )
    assert dataset["versions"][0]["memberships"][0]["decisions"] == []


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


def test_supervisor_registers_decision_and_reason(monkeypatch):
    database = setup_request(monkeypatch, "supervisor")
    try:
        response = client.post(
            f"/api/v1/datasets/memberships/{database.membership_id}/decisions",
            json={"decision": "rejected", "reason": "  Nubes densas  "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["decision"] == "rejected"
    assert response.json()["reason"] == "Nubes densas"
    assert response.json()["decided_by"] == database.user_id


# --- Pruebas de Transición de Estados ---

def test_valid_version_state_transitions():
    from app.datasets import validate_state_transition
    validate_state_transition(VersionState.DRAFT, VersionState.PUBLISHED)
    validate_state_transition(VersionState.DRAFT, VersionState.ARCHIVED)
    validate_state_transition(VersionState.PUBLISHED, VersionState.ARCHIVED)


def test_invalid_version_state_transitions_raise_400():
    from fastapi import HTTPException

    from app.datasets import validate_state_transition
    
    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.PUBLISHED, VersionState.DRAFT)
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        validate_state_transition(VersionState.ARCHIVED, VersionState.DRAFT)
    assert exc_info.value.status_code == 400


# --- Pruebas de Inmutabilidad S2-136 (Blindadas contra KeyError) ---

@pytest.mark.parametrize("state_to_test", ["PUBLISHED", "ARCHIVED"])
def test_incorporate_candidates_rejects_immutable_versions(monkeypatch, state_to_test):
    """Verifica que no se puedan modificar versiones consolidadas (S2-136)"""
    database = setup_request(monkeypatch, "admin")
    
    database.dataset_rows["versions"][0]["state"] = state_to_test
    database.dataset_rows["versions"][0]["status"] = state_to_test
    
    try:
        response = client.post(
            f"/api/v1/datasets/versions/{database.version_id}/candidates",
            json={"candidate_ids": [str(uuid4()), str(uuid4())]} 
        )
    finally:
        app.dependency_overrides.clear()
    
    assert response.status_code == 403
    # Soporte robusto tanto para estructura 'detail' como 'message'
    err_body = response.json()
    err_msg = err_body.get("detail", err_body.get("message", ""))
    assert "inmutable" in str(err_msg).lower()


def test_incorporate_candidates_allows_mutable_versions(monkeypatch):
    """Verifica que sí se pueda modificar una versión en estado DRAFT (S2-136)"""
    database = setup_request(monkeypatch, "admin")
    
    database.dataset_rows["versions"][0]["state"] = "DRAFT"
    database.dataset_rows["versions"][0]["status"] = "DRAFT"
    
    try:
        response = client.post(
            f"/api/v1/datasets/versions/{database.version_id}/candidates",
            json={"candidate_ids": [str(uuid4())]} 
        )
    finally:
        app.dependency_overrides.clear()
    
    assert response.status_code == 201
    assert response.json()["count"] == 1



