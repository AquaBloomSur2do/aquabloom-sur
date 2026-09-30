import os
from types import SimpleNamespace

from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")

from app.auth import verify_supabase_jwt
from app.main import app


class FakeCountQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name

    def select(self, columns, **kwargs):
        self.client.queries.append(
            {
                "table": self.table_name,
                "columns": columns,
                "options": kwargs,
                "filters": [],
            }
        )
        self.query = self.client.queries[-1]
        return self

    def eq(self, field, value):
        self.query["filters"].append((field, value))
        return self

    def execute(self):
        return SimpleNamespace(count=self.client.counts[self.table_name])


class FakeCountClient:
    def __init__(self, counts):
        self.counts = counts
        self.queries = []

    def table(self, table_name):
        return FakeCountQuery(self, table_name)


def test_dashboard_summary_returns_exact_counts_for_authenticated_admin(monkeypatch):
    fake_supabase = FakeCountClient({"lakes": 17, "stations": 42, "organizations": 5})
    payload = {"sub": "admin-user", "user_metadata": {"role": "administrador"}}
    app.dependency_overrides[verify_supabase_jwt] = lambda: payload
    monkeypatch.setattr("app.dashboard.supabase", fake_supabase)

    try:
        response = TestClient(app).get("/api/v1/dashboard/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "active_lakes_count": 17,
        "active_stations_count": 42,
        "visible_organizations_count": 5,
    }
    assert [query["table"] for query in fake_supabase.queries] == [
        "lakes",
        "stations",
        "organizations",
    ]
    assert all(
        query["options"] == {"count": "exact", "head": True}
        for query in fake_supabase.queries
    )
    assert all(query["columns"] == "id" for query in fake_supabase.queries)
    assert fake_supabase.queries[0]["filters"] == [("status", "active")]
    assert fake_supabase.queries[1]["filters"] == [("status", "active")]
    assert fake_supabase.queries[2]["filters"] == [("status", "active")]


def test_dashboard_summary_counts_only_user_visible_organizations(monkeypatch):
    fake_supabase = FakeCountClient({"lakes": 3, "stations": 8, "memberships": 2})
    payload = {"sub": "member-user", "user_metadata": {"role": "investigador"}}
    app.dependency_overrides[verify_supabase_jwt] = lambda: payload
    monkeypatch.setattr("app.dashboard.supabase", fake_supabase)

    try:
        response = TestClient(app).get("/api/v1/dashboard/summary")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "active_lakes_count": 3,
        "active_stations_count": 8,
        "visible_organizations_count": 2,
    }
    membership_query = fake_supabase.queries[2]
    assert membership_query["table"] == "memberships"
    assert membership_query["columns"] == "organization_id, organizations!inner(id)"
    assert membership_query["filters"] == [
        ("user_id", "member-user"),
        ("status", "active"),
        ("organizations.status", "active"),
    ]
    assert membership_query["options"] == {"count": "exact", "head": True}


def test_dashboard_summary_requires_authentication():
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/v1/dashboard/summary")
    assert response.status_code == 401
