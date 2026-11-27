import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.domains.library import controller_library
from apps.api.app.main import app
from apps.api.tests.test_openapi_contracts import assert_response_matches_openapi

USER_ID = "11111111-1111-4111-8111-111111111111"
RESOURCE_ID = "22222222-2222-4222-8222-222222222222"


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeLibraryVersionsTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._insert_payload: dict | None = None
        self._filters: dict[str, object] = {}

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: object):
        self._filters[field] = value
        return self

    def limit(self, _count: int):
        return self

    def insert(self, payload: dict):
        self._insert_payload = payload
        return self

    def execute(self):
        if self._insert_payload is not None:
            row = {
                "id": str(uuid.uuid4()),
                "resource_id": self._insert_payload["resource_id"],
                "status": self._insert_payload.get("status", "draft"),
                "attribution": dict(self._insert_payload["attribution"]),
                "created_by": self._insert_payload.get("created_by"),
                "created_at": datetime.now(UTC).isoformat(),
            }
            self._rows.append(row)
            return FakeResponse([row])

        matched = [
            row
            for row in self._rows
            if all(row.get(k) == v for k, v in self._filters.items())
        ]
        return FakeResponse(matched)


class FakeLibrarySchema:
    def __init__(self, rows: list[dict]):
        self._rows = rows

    def table(self, table_name: str):
        assert table_name == "versions"
        return FakeLibraryVersionsTable(self._rows)


class FakeSupabaseClient:
    def __init__(self):
        self.rows: list[dict] = []

    def schema(self, schema_name: str):
        assert schema_name == "library"
        return FakeLibrarySchema(self.rows)


@pytest.fixture
def library_client(monkeypatch):
    fake_db = FakeSupabaseClient()
    monkeypatch.setattr(controller_library, "supabase", fake_db)
    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: {"sub": USER_ID},
    )
    yield TestClient(app), fake_db
    app.dependency_overrides.pop(verify_supabase_jwt, None)


def _valid_attribution() -> dict:
    return {
        "author": {
            "status": "known",
            "name": "María Pérez",
            "orcid": "0000-0002-1825-0097",
        },
        "license": {
            "spdx_id": "CC-BY-4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        },
        "version": "1.2.0",
        "source": {
            "name": "Repositorio de datos del Lago Azul",
            "url": "https://example.org/datasets/lago-azul",
        },
    }


def test_rejects_version_without_license_property(library_client):
    client, fake_db = library_client
    attribution = _valid_attribution()
    del attribution["license"]

    response = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": attribution},
    )

    assert response.status_code == 422
    assert not fake_db.rows


def test_rejects_version_without_source_or_empty_source_name(library_client):
    client, fake_db = library_client

    missing_source = _valid_attribution()
    del missing_source["source"]
    res_missing = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": missing_source},
    )
    assert res_missing.status_code == 422

    blank_source_name = _valid_attribution()
    blank_source_name["source"] = {"name": "   ", "url": None}
    res_blank = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": blank_source_name},
    )
    assert res_blank.status_code == 422
    assert not fake_db.rows


def test_creates_and_reads_valid_version_preserving_license_and_source(
    library_client,
):
    client, fake_db = library_client
    attribution = _valid_attribution()

    create_res = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": attribution},
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["resource_id"] == RESOURCE_ID
    assert created["status"] == "draft"
    assert created["attribution"] == attribution
    assert created["created_by"] == USER_ID
    assert len(fake_db.rows) == 1

    assert_response_matches_openapi(
        client, "/api/v1/library/versions", "post", 201, created
    )

    version_id = created["id"]
    get_res = client.get(f"/api/v1/library/versions/{version_id}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert fetched["attribution"]["license"] == attribution["license"]
    assert fetched["attribution"]["source"] == attribution["source"]

    assert_response_matches_openapi(
        client, "/api/v1/library/versions/{version_id}", "get", 200, fetched
    )


def test_accepts_explicit_null_license_and_preserves_it(library_client):
    client, _fake_db = library_client
    attribution = {
        "author": {"status": "unknown", "name": None},
        "license": None,
        "version": "1.0.0",
        "source": {
            "name": "Importación histórica de biblioteca",
            "url": None,
        },
    }

    create_res = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": attribution},
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert "license" in created["attribution"]
    assert created["attribution"]["license"] is None
    assert (
        created["attribution"]["source"]["name"]
        == "Importación histórica de biblioteca"
    )

    get_res = client.get(f"/api/v1/library/versions/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["attribution"]["license"] is None
