from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_organization_members_requires_active_membership(monkeypatch):
    requester_id = uuid4()
    organization_id = uuid4()

    def fake_get_authenticated_user(token):
        return requester_id, "member@example.com"

    async def fake_get_organization_members_for_user(client, user_id, org_id):
        raise PermissionError("Usuario no pertenece a la organización")

    monkeypatch.setattr(
        "app.organizations.get_authenticated_user", fake_get_authenticated_user
    )
    monkeypatch.setattr(
        "app.organizations.get_organization_members_for_user",
        fake_get_organization_members_for_user,
    )

    response = client.get(
        f"/api/v1/organizations/{organization_id}/members",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 403


def test_get_organization_members_returns_not_found_for_missing_org(monkeypatch):
    requester_id = uuid4()
    organization_id = uuid4()

    def fake_get_authenticated_user(token):
        return requester_id, "member@example.com"

    async def fake_get_organization_members_for_user(client, user_id, org_id):
        raise LookupError("Organización no encontrada")

    monkeypatch.setattr(
        "app.organizations.get_authenticated_user", fake_get_authenticated_user
    )
    monkeypatch.setattr(
        "app.organizations.get_organization_members_for_user",
        fake_get_organization_members_for_user,
    )

    response = client.get(
        f"/api/v1/organizations/{organization_id}/members",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 404
