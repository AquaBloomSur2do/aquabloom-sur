import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.domains.library import controller_library
from apps.api.app.domains.library.model_library import APIError
from apps.api.app.main import app
from apps.api.tests.test_openapi_contracts import assert_response_matches_openapi

USER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_USER_ID = "99999999-9999-4999-8999-999999999999"
ORG_ID = "33333333-3333-4333-8333-333333333333"
OTHER_ORG_ID = "44444444-4444-4444-8444-444444444444"
RESOURCE_ID = "22222222-2222-4222-8222-222222222222"
PUBLIC_RESOURCE_ID = "55555555-5555-4555-8555-555555555555"
OTHER_ORG_RESOURCE_ID = "66666666-6666-4666-8666-666666666666"


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, table_name: str, db: "FakeSupabaseClient"):
        self._table_name = table_name
        self._db = db
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
        if self._table_name == "resource_versions" and self._db.next_insert_error is not None:
            err = self._db.next_insert_error
            self._db.next_insert_error = None
            raise err

        rows = self._db.tables[self._table_name]
        if self._insert_payload is not None:
            if self._table_name == "resource_versions":
                for existing in rows:
                    if (
                        existing["resource_id"] == self._insert_payload["resource_id"]
                        and existing["version"] == self._insert_payload["version"]
                    ):
                        raise APIError({"code": "23505", "message": "duplicate key"})

            row = {
                "id": str(uuid.uuid4()),
                "created_at": datetime.now(UTC).isoformat(),
                **dict(self._insert_payload),
            }
            rows.append(row)
            return FakeResponse([row])

        matched = [
            row
            for row in rows
            if all(str(row.get(k)) == str(v) for k, v in self._filters.items())
        ]
        return FakeResponse(matched)


class FakeSchema:
    def __init__(self, schema_name: str, db: "FakeSupabaseClient"):
        self._schema_name = schema_name
        self._db = db

    def table(self, table_name: str):
        assert self._schema_name == "library"
        assert table_name in {"resources", "resource_versions"}
        return FakeTable(table_name, self._db)


class FakeSupabaseClient:
    def __init__(self):
        self.next_insert_error: Exception | None = None
        self.tables: dict[str, list[dict]] = {
            "resources": [
                {
                    "id": RESOURCE_ID,
                    "owner_organization_id": ORG_ID,
                    "visibility": "private",
                },
                {
                    "id": PUBLIC_RESOURCE_ID,
                    "owner_organization_id": ORG_ID,
                    "visibility": "public",
                },
                {
                    "id": OTHER_ORG_RESOURCE_ID,
                    "owner_organization_id": OTHER_ORG_ID,
                    "visibility": "private",
                },
            ],
            "resource_versions": [],
            "memberships": [
                {
                    "id": str(uuid.uuid4()),
                    "organization_id": ORG_ID,
                    "user_id": USER_ID,
                    "role": "author",
                    "status": "active",
                },
            ],
        }

    @property
    def rows(self) -> list[dict]:
        return self.tables["resource_versions"]

    def schema(self, schema_name: str):
        return FakeSchema(schema_name, self)

    def table(self, table_name: str):
        assert table_name == "memberships"
        return FakeTable("memberships", self)


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
    assert fake_db.rows[0]["version"] == "1.2.0"

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


def test_rejects_unauthenticated_and_invalid_jwt_subject(monkeypatch):
    fake_db = FakeSupabaseClient()
    monkeypatch.setattr(controller_library, "supabase", fake_db)
    app.dependency_overrides.pop(verify_supabase_jwt, None)
    client = TestClient(app)

    unauth_res = client.get(f"/api/v1/library/versions/{uuid.uuid4()}")
    assert unauth_res.status_code == 401

    monkeypatch.setitem(app.dependency_overrides, verify_supabase_jwt, lambda: {"role": "authenticated"})
    missing_sub_res = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": _valid_attribution()},
    )
    assert missing_sub_res.status_code == 401

    monkeypatch.setitem(
        app.dependency_overrides, verify_supabase_jwt, lambda: {"sub": "not-a-uuid"}
    )
    invalid_sub_res = client.get(f"/api/v1/library/versions/{uuid.uuid4()}")
    assert invalid_sub_res.status_code == 401
    app.dependency_overrides.pop(verify_supabase_jwt, None)


def test_enforces_organization_and_role_access_controls(library_client, monkeypatch):
    client, fake_db = library_client

    # Miembro activo con rol no autorizado para crear versiones (reviewer -> 403)
    fake_db.tables["memberships"][0]["role"] = "reviewer"
    forbidden_res = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": _valid_attribution()},
    )
    assert forbidden_res.status_code == 403
    assert not fake_db.rows

    # Recurso de otra organización -> 404 para evitar enumeración
    other_org_post = client.post(
        "/api/v1/library/versions",
        json={
            "resource_id": OTHER_ORG_RESOURCE_ID,
            "attribution": _valid_attribution(),
        },
    )
    assert other_org_post.status_code == 404

    # Crear borrador como org_admin y bloquear lectura IDOR a usuario externo
    fake_db.tables["memberships"][0]["role"] = "org_admin"
    created = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": _valid_attribution()},
    ).json()

    monkeypatch.setitem(
        app.dependency_overrides,
        verify_supabase_jwt,
        lambda: {"sub": OTHER_USER_ID},
    )
    idor_draft_res = client.get(f"/api/v1/library/versions/{created['id']}")
    assert idor_draft_res.status_code == 404

    # Una versión published de un recurso public sí es legible por cualquier autenticado
    public_version_id = str(uuid.uuid4())
    attr = _valid_attribution()
    fake_db.rows.append(
        {
            "id": public_version_id,
            "resource_id": PUBLIC_RESOURCE_ID,
            "version": "2.0.0",
            "status": "published",
            "author": attr["author"],
            "license": attr["license"],
            "source": attr["source"],
            "created_by": USER_ID,
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    public_read_res = client.get(f"/api/v1/library/versions/{public_version_id}")
    assert public_read_res.status_code == 200
    assert public_read_res.json()["id"] == public_version_id

    # Versión inexistente -> 404
    missing_res = client.get(f"/api/v1/library/versions/{uuid.uuid4()}")
    assert missing_res.status_code == 404


def test_validation_edge_cases_and_jsonable_422_serialization(library_client):
    client, fake_db = library_client

    # Sin license
    no_license = _valid_attribution()
    del no_license["license"]
    assert (
        client.post(
            "/api/v1/library/versions",
            json={"resource_id": RESOURCE_ID, "attribution": no_license},
        ).status_code
        == 422
    )

    # Sin source o con source.name vacío
    no_source = _valid_attribution()
    del no_source["source"]
    assert (
        client.post(
            "/api/v1/library/versions",
            json={"resource_id": RESOURCE_ID, "attribution": no_source},
        ).status_code
        == 422
    )

    blank_source = _valid_attribution()
    blank_source["source"] = {"name": "   ", "url": None}
    res_blank_source = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": blank_source},
    )
    assert res_blank_source.status_code == 422
    assert res_blank_source.json()["error"] == "Validation Error"

    # License con spdx_id vacío
    blank_spdx = _valid_attribution()
    blank_spdx["license"] = {"spdx_id": "   ", "url": None}
    assert (
        client.post(
            "/api/v1/library/versions",
            json={"resource_id": RESOURCE_ID, "attribution": blank_spdx},
        ).status_code
        == 422
    )

    # Autor unknown con name o con orcid
    unknown_with_name = _valid_attribution()
    unknown_with_name["author"] = {"status": "unknown", "name": "Alguien"}
    assert (
        client.post(
            "/api/v1/library/versions",
            json={"resource_id": RESOURCE_ID, "attribution": unknown_with_name},
        ).status_code
        == 422
    )

    unknown_with_orcid = _valid_attribution()
    unknown_with_orcid["author"] = {
        "status": "unknown",
        "name": None,
        "orcid": "0000-0002-1825-0097",
    }
    res_unknown_orcid = client.post(
        "/api/v1/library/versions",
        json={"resource_id": RESOURCE_ID, "attribution": unknown_with_orcid},
    )
    assert res_unknown_orcid.status_code == 422
    assert isinstance(res_unknown_orcid.json()["details"], list)

    # SemVer con ceros a la izquierda
    leading_zero_semver = _valid_attribution()
    leading_zero_semver["version"] = "01.02.03"
    assert (
        client.post(
            "/api/v1/library/versions",
            json={"resource_id": RESOURCE_ID, "attribution": leading_zero_semver},
        ).status_code
        == 422
    )

    # URL inválida (no http/https)
    bad_url = _valid_attribution()
    bad_url["source"]["url"] = "ftp://example.org/file.csv"
    assert (
        client.post(
            "/api/v1/library/versions",
            json={"resource_id": RESOURCE_ID, "attribution": bad_url},
        ).status_code
        == 422
    )

    # Campo extra prohibido (extra="forbid")
    extra_field = _valid_attribution()
    extra_field["unexpected"] = "nope"
    assert (
        client.post(
            "/api/v1/library/versions",
            json={"resource_id": RESOURCE_ID, "attribution": extra_field},
        ).status_code
        == 422
    )

    assert not fake_db.rows


def test_database_error_mapping_and_unavailable_db(library_client, monkeypatch):
    client, fake_db = library_client
    payload = {"resource_id": RESOURCE_ID, "attribution": _valid_attribution()}

    # 409 por duplicado (23505)
    assert client.post("/api/v1/library/versions", json=payload).status_code == 201
    conflict_res = client.post("/api/v1/library/versions", json=payload)
    assert conflict_res.status_code == 409

    # 404 por llave foránea (23503)
    fake_db.next_insert_error = APIError({"code": "23503"})
    payload["attribution"]["version"] = "2.0.0"
    assert client.post("/api/v1/library/versions", json=payload).status_code == 404

    # 422 por CHECK constraint (23514)
    fake_db.next_insert_error = APIError({"code": "23514"})
    assert client.post("/api/v1/library/versions", json=payload).status_code == 422

    # 503 cuando supabase es None
    monkeypatch.setattr(controller_library, "supabase", None)
    assert client.post("/api/v1/library/versions", json=payload).status_code == 503
