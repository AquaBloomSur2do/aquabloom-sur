import pytest
from fastapi.testclient import TestClient

import app.lakes as lakes_module
import app.scenes as scenes_module
from app.auth import verify_supabase_jwt
from app.main import app

LAKE_ID = "11111111-1111-1111-1111-111111111111"
AUTH_HEADER = {"Authorization": "Bearer fake_token"}


class FakeQueryBuilder:
    def __init__(self, table_name, data=None):
        self.table_name = table_name
        self._data = data if data is not None else []
        self._filtered_data = list(self._data)

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        if column == "id":
            self._filtered_data = [
                row for row in self._filtered_data if str(row.get("id")) == str(value)
            ]
        elif column == "lake_id":
            self._filtered_data = [
                row for row in self._filtered_data if str(row.get("lake_id")) == str(value)
            ]
        return self

    def gte(self, column, value):
        if column == "acquisition_date":
            self._filtered_data = [
                row for row in self._filtered_data if str(row.get("acquisition_date")) >= str(value)
            ]
        return self

    def lte(self, column, value):
        if column == "acquisition_date":
            self._filtered_data = [
                row for row in self._filtered_data if str(row.get("acquisition_date")) <= str(value)
            ]
        return self

    def order(self, column, desc=False):
        self._filtered_data.sort(
            key=lambda x: x.get(column, ""),
            reverse=desc,
        )
        return self

    def range(self, start, end):
        self._filtered_data = self._filtered_data[start : end + 1]
        return self

    def limit(self, count):
        self._filtered_data = self._filtered_data[:count]
        return self

    def execute(self):
        class Response:
            def __init__(self, data, count):
                self.data = data
                self.count = count

        return Response(self._filtered_data, len(self._filtered_data))


class FakeSupabase:
    def __init__(self):
        self.lakes_data = [{"id": LAKE_ID, "name": "Lago Piloto"}]
        self.scenes_data = [
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "lake_id": LAKE_ID,
                "scene_identifier": "S2A_MSIL2A_20260320T142701",
                "acquisition_date": "2026-03-20",
                "created_at": "2026-03-20T15:00:00Z",
            },
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "lake_id": LAKE_ID,
                "scene_identifier": "S2A_MSIL2A_20260310T142701",
                "acquisition_date": "2026-03-10",
                "created_at": "2026-03-10T15:00:00Z",
            },
        ]

    def table(self, table_name):
        if table_name == "lakes":
            return FakeQueryBuilder("lakes", self.lakes_data)
        elif table_name == "scenes":
            return FakeQueryBuilder("scenes", self.scenes_data)
        return FakeQueryBuilder(table_name, [])


@pytest.fixture
def scenes_client(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(scenes_module, "supabase", fake_db)
    monkeypatch.setattr(lakes_module, "supabase", fake_db)

    app.dependency_overrides[verify_supabase_jwt] = lambda: {
        "sub": "123e4567-e89b-12d3-a456-426614174000"
    }

    yield TestClient(app), fake_db

    app.dependency_overrides.clear()


def test_list_scenes_filters_by_lake_and_inclusive_date_range(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        params={
            "start_date": "2026-03-20",
            "end_date": "2026-03-20",
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["acquisition_date"] == "2026-03-20"


def test_list_scenes_is_paginated_and_ordered_newest_first(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "page_size": 1,
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["acquisition_date"] == "2026-03-20"


def test_list_scenes_rejects_reversed_date_range(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        params={
            "start_date": "2026-03-31",
            "end_date": "2026-03-01",
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code in (400, 422)


def test_list_scenes_requires_bounded_date_range(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        headers=AUTH_HEADER,
    )

    assert response.status_code == 422


def test_list_scenes_rejects_page_size_over_maximum(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "page_size": 101,
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 422


def test_list_scenes_returns_not_found_for_unknown_lake(scenes_client):
    client, _ = scenes_client
    unknown_lake_id = "33333333-3333-3333-3333-333333333333"

    response = client.get(
        f"/api/v1/lakes/{unknown_lake_id}/scenes",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
        headers=AUTH_HEADER,
    )

    assert response.status_code == 404
    
