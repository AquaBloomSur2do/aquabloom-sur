from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import verify_supabase_jwt
from app.main import app

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
