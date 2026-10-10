from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import verify_supabase_jwt
from app.main import app
from app.services import get_organization_members_for_user

client = TestClient(app)


def test_get_organization_members_requires_active_membership(monkeypatch):
    requester_id = uuid4()
    organization_id = uuid4()

    app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "sub": str(requester_id),
        "email": "member@example.com",
    }

    def fake_get_organization_members_for_user(client_db, user_id, org_id):
        raise PermissionError("Usuario no pertenece a la organización")

    monkeypatch.setattr(
        "app.organizations.get_organization_members_for_user",
        fake_get_organization_members_for_user,
    )

    try:
        response = client.get(
            f"/api/v1/organizations/{organization_id}/members",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_get_organization_members_returns_not_found_for_missing_org(monkeypatch):
    requester_id = uuid4()
    organization_id = uuid4()

    app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "sub": str(requester_id),
        "email": "member@example.com",
    }

    def fake_get_organization_members_for_user(client_db, user_id, org_id):
        raise LookupError("Organización no encontrada")

    monkeypatch.setattr(
        "app.organizations.get_organization_members_for_user",
        fake_get_organization_members_for_user,
    )

    try:
        response = client.get(
            f"/api/v1/organizations/{organization_id}/members",
            headers={"Authorization": "Bearer fake-token"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_organization_members_maps_profile_name_to_full_name():
    user_id = uuid4()
    organization_id = uuid4()
    membership_id = uuid4()

    class FakeQuery:
        def __init__(self, table_name):
            self.table_name = table_name
            self.selection = ""
            self.ids = []

        def select(self, selection):
            self.selection = selection
            return self

        def eq(self, *_args):
            return self

        def maybe_single(self):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def in_(self, _field, values):
            self.ids = values
            return self

        def execute(self):
            if self.table_name == "organizations":
                return SimpleNamespace(data={"id": str(organization_id)})
            if self.table_name == "profiles":
                return SimpleNamespace(
                    data=[
                        {
                            "id": str(user_id),
                            "name": "Ana Ejemplo",
                            "email": "ana@example.test",
                        }
                    ]
                )
            if self.selection == "id, role, status":
                return SimpleNamespace(data={"id": str(membership_id)})
            return SimpleNamespace(
                data=[
                    {
                        "user_id": str(user_id),
                        "role": "researcher",
                        "status": "active",
                        "created_at": datetime.now(UTC).isoformat(),
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                ]
            )

    class FakeClient:
        def table(self, table_name):
            return FakeQuery(table_name)

    members = get_organization_members_for_user(FakeClient(), user_id, organization_id)

    assert members[0]["full_name"] == "Ana Ejemplo"
    assert members[0]["email"] == "ana@example.test"
