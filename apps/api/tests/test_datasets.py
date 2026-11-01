import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth import verify_supabase_jwt
from app.datasets import APIError, validate_state_transition
from app.main import app
from app.schemas import DatasetVersionStateUpdate
from dataset.application.schemas import VersionState

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
# Pruebas S2-105 / S2-134 / S2-136: Endpoints y Supabase Mock
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
        self._range = None
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
        self._range = (start, end)
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
            if self._range is not None:
                start, end = self._range
                rows = rows[start:end + 1]
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

        if self._range is not None and self.table_name in ["datasets", "versions", "memberships", "decisions"]:
            start, end = self._range
            rows = rows[start:end + 1]

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
        # Usando UUIDs válidos para evitar HTTP 422 (Solución S2-136)
        self.dataset_id = str(uuid4())
        self.dataset_id_2 = str(uuid4())
        self.organization_id = str(uuid4())
        self.version_id = str(uuid4())
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
                    "name": "Dataset piloto 1",
                    "description": None,
                    "created_at": "2026-10-27T00:00:00+00:00",
                },
                {
                    "id": self.dataset_id_2,
                    "organization_id": self.organization_id,
                    "name": "Dataset piloto 2",
                    "description": None,
                    "created_at": "2026-10-28T00:00:00+00:00",
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


# --- Pruebas S2-105 / S2-134: Endpoints y Paginación ---

def test_list_review_datasets_returns_paginated_structure(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    try:
        response = client.get("/api/v1/datasets/review?page=1&page_size=1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == database.dataset_id
    assert data["has_more"] is True


def test_list_review_datasets_pagination_successive_pages(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    try:
        resp_p1 = client.get("/api/v1/datasets/review?page=1&page_size=1")
        resp_p2 = client.get("/api/v1/datasets/review?page=2&page_size=1")
    finally:
        app.dependency_overrides.clear()

    assert resp_p1.status_code == 200
    assert resp_p2.status_code == 200

    item_p1 = resp_p1.json()["items"][0]["id"]
    item_p2 = resp_p2.json()["items"][0]["id"]

    assert item_p1 != item_p2
    assert item_p1 == database.dataset_id
    assert item_p2 == database.dataset_id_2


def test_list_review_datasets_paginates_versions(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    second_version_id = str(uuid4())
    database.dataset_rows["versions"].append(
        {
            "id": second_version_id,
            "dataset_id": database.dataset_id,
            "version_number": 2,
            "state": "DRAFT",
            "status": "DRAFT",
            "created_at": "2026-10-28T00:00:00+00:00",
        }
    )
    try:
        resp_v1 = client.get("/api/v1/datasets/review?version_page=1&version_page_size=1")
        resp_v2 = client.get("/api/v1/datasets/review?version_page=2&version_page_size=1")
    finally:
        app.dependency_overrides.clear()

    assert resp_v1.status_code == 200
    assert resp_v2.status_code == 200
    v1_id = resp_v1.json()["items"][0]["versions"][0]["id"]
    v2_id = resp_v2.json()["items"][0]["versions"][0]["id"]
    assert v1_id != v2_id


def test_list_review_datasets_paginates_decisions(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    database.dataset_rows["decisions"] = [
        {
            "id": "dec-1",
            "membership_id": database.membership_id,
            "decision": "accepted",
            "reason": "OK",
            "decided_by": database.user_id,
            "decided_at": "2026-10-27T00:00:00+00:00",
        },
        {
            "id": "dec-2",
            "membership_id": database.membership_id,
            "decision": "rejected",
            "reason": "Bad",
            "decided_by": database.user_id,
            "decided_at": "2026-10-26T00:00:00+00:00",
        },
    ]
    try:
        resp_d1 = client.get("/api/v1/datasets/review?decision_page=1&decision_page_size=1")
        resp_d2 = client.get("/api/v1/datasets/review?decision_page=2&decision_page_size=1")
    finally:
        app.dependency_overrides.clear()

    assert resp_d1.status_code == 200
    assert resp_d2.status_code == 200
    d1_id = resp_d1.json()["items"][0]["versions"][0]["memberships"][0]["decisions"][0]["id"]
    d2_id = resp_d2.json()["items"][0]["versions"][0]["memberships"][0]["decisions"][0]["id"]
    assert d1_id != d2_id


def test_list_review_datasets_paginates_organization_memberships(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    second_organization_id = str(uuid4())
    database.organization_memberships.append(
        {
            "user_id": database.user_id,
            "organization_id": second_organization_id,
            "role": "investigador",
            "status": "active",
        }
    )
    try:
        resp_org1 = client.get("/api/v1/datasets/review?org_membership_page=1&org_membership_page_size=1")
        resp_org2 = client.get("/api/v1/datasets/review?org_membership_page=2&org_membership_page_size=1")
    finally:
        app.dependency_overrides.clear()

    assert resp_org1.status_code == 200
    assert resp_org2.status_code == 200
    assert resp_org1.json()["org_membership_page"] == 1
    assert resp_org2.json()["org_membership_page"] == 2


def test_list_review_datasets_preserves_exact_state_without_mutation(monkeypatch):
    setup_request(monkeypatch, "investigador")
    try:
        response = client.get("/api/v1/datasets/review")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    version_obj = data["items"][0]["versions"][0]
    assert version_obj["state"] == "DRAFT"
    assert version_obj["status"] == "DRAFT"


def test_list_review_datasets_handles_version_without_memberships(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    database.dataset_rows["memberships"] = []
    try:
        response = client.get("/api/v1/datasets/review")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"][0]["versions"][0]["memberships"]) == 0


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
    database.organization_memberships[0]["organization_id"] = str(uuid4())
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


def test_publishing_version_creates_small_versioned_training_file_and_manifest(monkeypatch):
    database = setup_request(monkeypatch, "admin")
    database.dataset_rows["versions"][0]["state"] = "APPROVED"
    database.dataset_rows["versions"][0]["status"] = "APPROVED"
    uploaded = {}

    class FakeBucket:
        def upload(self, path, content, file_options):
            uploaded.update(
                path=path,
                content=content,
                file_options=file_options,
            )

    class FakeStorage:
        def from_(self, name):
            assert name == "training_files"
            return FakeBucket()

    database.storage = FakeStorage()
    try:
        response = client.patch(
            f"/api/v1/datasets/versions/{database.version_id}/state",
            json={"state": "PUBLISHED"},
        )
    finally:
        app.dependency_overrides.clear()

    expected_content = b"temperatura,clorofila_a,turbidez,ph\r\n15.5,2.1,0.5,7.2\r\n"
    assert response.status_code == 200
    assert uploaded["path"] == f"versions/{database.version_id}/training.csv"
    assert uploaded["content"] == expected_content
    assert len(uploaded["content"]) <= 1024 * 1024
    manifest = database.dataset_rows["training_manifests"][0]
    assert manifest["version_id"] == database.version_id
    assert manifest["storage_path"] == uploaded["path"]
    assert manifest["checksum"] == hashlib.sha256(expected_content).hexdigest()

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

# --- Pruebas S2-137: Descarga Estricta de Archivo de Entrenamiento ---

def test_training_file_generation_and_strict_download(monkeypatch):
    database = setup_request(monkeypatch, "investigador")

    # Simular que el archivo se generó al publicar
    csv_content = b"temperatura,clorofila_a,turbidez,ph\r\n15.5,2.1,0.5,7.2\r\n"
    real_sha256 = hashlib.sha256(csv_content).hexdigest()

    database.dataset_rows["versions"][0]["state"] = "PUBLISHED"
    database.dataset_rows["training_manifests"] = [{
        "id": "55555555-5555-5555-5555-555555555555",
        "version_id": database.version_id,
        "storage_path": f"versions/{database.version_id}/training.csv",
        "checksum": real_sha256,
        "variables": ["temperatura", "clorofila_a", "turbidez", "ph"]
    }]

    # Mockear Storage para devolver los bytes exactos
    class FakeBucket:
        def download(self, path):
            return csv_content

    class FakeStorage:
        def from_(self, name):
            return FakeBucket()

    database.storage = FakeStorage()

    try:
        # 1. Probar metadatos y variables dinámicas
        res_meta = client.get(f"/api/v1/datasets/versions/{database.version_id}/training-file")
        assert res_meta.status_code == 200
        data = res_meta.json()
        assert data["checksum"] == real_sha256
        assert data["manifest_id"] == "55555555-5555-5555-5555-555555555555"
        assert data["download_url"].endswith("/download")
        assert data["variables"] == [
            "temperatura",
            "clorofila_a",
            "turbidez",
            "ph",
        ]

        # 2. Probar descarga estricta (Proxy)
        res_download = client.get(data["download_url"])
        assert res_download.status_code == 200
        assert res_download.content == csv_content
        # Confirmar que el checksum del archivo real devuelto es idéntico al manifiesto
        assert hashlib.sha256(res_download.content).hexdigest() == real_sha256
        assert res_download.headers["Content-Disposition"] == f'attachment; filename="training_{database.version_id}.csv"'
    finally:
        app.dependency_overrides.clear()


def test_get_training_file_denied_if_not_published(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    database.dataset_rows["versions"][0]["state"] = "DRAFT"
    try:
        res = client.get(f"/api/v1/datasets/versions/{database.version_id}/training-file")
        res_down = client.get(f"/api/v1/datasets/versions/{database.version_id}/training-file/download")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403
    assert res_down.status_code == 403


def test_get_training_file_denied_wrong_org(monkeypatch):
    database = setup_request(monkeypatch, "admin")
    database.dataset_rows["versions"][0]["state"] = "PUBLISHED"
    database.organization_memberships[0]["organization_id"] = str(uuid4())
    try:
        res = client.get(f"/api/v1/datasets/versions/{database.version_id}/training-file")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 403


def test_get_training_file_denied_for_unapproved_role(monkeypatch):
    database = setup_request(monkeypatch, "member")
    database.dataset_rows["versions"][0]["state"] = "PUBLISHED"
    try:
        response = client.get(
            f"/api/v1/datasets/versions/{database.version_id}/training-file"
        )
        download_response = client.get(
            f"/api/v1/datasets/versions/{database.version_id}/training-file/download"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert download_response.status_code == 403


def test_training_file_download_rejects_checksum_mismatch(monkeypatch):
    database = setup_request(monkeypatch, "investigador")
    database.dataset_rows["versions"][0]["state"] = "PUBLISHED"
    database.dataset_rows["training_manifests"] = [
        {
            "id": "55555555-5555-5555-5555-555555555555",
            "version_id": database.version_id,
            "storage_path": f"versions/{database.version_id}/training.csv",
            "checksum": "0" * 64,
            "variables": ["temperatura", "clorofila_a", "turbidez", "ph"],
        }
    ]

    class FakeBucket:
        def download(self, path):
            return b"temperatura,clorofila_a,turbidez,ph\r\n"

    class FakeStorage:
        def from_(self, name):
            return FakeBucket()

    database.storage = FakeStorage()
    try:
        response = client.get(
            f"/api/v1/datasets/versions/{database.version_id}/training-file/download"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502

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




