import os
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from app import lakes as lakes_module
from app.main import app

LAKE_ID = "11111111-1111-1111-1111-111111111111"
OTHER_LAKE_ID = "22222222-2222-2222-2222-222222222222"


class FakeResponse:
    def __init__(self, data, count=None):
        self.data = data
        self.count = len(data) if count is None else count


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.filters = []
        self.ordering = None
        self.page_range = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters.append((field, "eq", value))
        return self

    def gte(self, field, value):
        self.filters.append((field, "gte", value))
        return self

    def lte(self, field, value):
        self.filters.append((field, "lte", value))
        return self

    def order(self, field, desc=False):
        self.ordering = (field, desc)
        return self

    def limit(self, _limit):
        return self

    def range(self, start, end):
        self.page_range = (start, end)
        return self

    def execute(self):
        items = list(self.database.tables.get(self.table_name, []))

        for field, operator, value in self.filters:
            if operator == "eq":
                items = [item for item in items if str(item.get(field)) == value]
            elif operator == "gte":
                items = [item for item in items if item.get(field, "") >= value]
            elif operator == "lte":
                items = [item for item in items if item.get(field, "") <= value]

        if self.ordering:
            field, descending = self.ordering
            items.sort(key=lambda item: item[field], reverse=descending)

        total = len(items)
        if self.page_range:
            start, end = self.page_range
            items = items[start : end + 1]

        return FakeResponse(items, total)


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "lakes": [{"id": LAKE_ID}],
            "scenes": [
                {
                    "id": str(uuid.uuid4()),
                    "lake_id": LAKE_ID,
                    "scene_identifier": "scene-early",
                    "acquisition_date": "2026-03-10",
                    "created_at": "2026-03-10T10:00:00Z",
                },
                {
                    "id": str(uuid.uuid4()),
                    "lake_id": LAKE_ID,
                    "scene_identifier": "scene-in-range",
                    "acquisition_date": "2026-03-20",
                    "created_at": "2026-03-20T10:00:00Z",
                },
                {
                    "id": str(uuid.uuid4()),
                    "lake_id": LAKE_ID,
                    "scene_identifier": "scene-late",
                    "acquisition_date": "2026-03-30",
                    "created_at": "2026-03-30T10:00:00Z",
                },
                {
                    "id": str(uuid.uuid4()),
                    "lake_id": OTHER_LAKE_ID,
                    "scene_identifier": "scene-other-lake",
                    "acquisition_date": "2026-03-20",
                    "created_at": "2026-03-20T10:00:00Z",
                },
            ],
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


@pytest.fixture
def scenes_client(monkeypatch):
    fake_db = FakeSupabase()
    monkeypatch.setattr(lakes_module, "supabase", fake_db)
    return TestClient(app), fake_db


def test_list_scenes_filters_by_lake_and_inclusive_date_range(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        params={
            "start_date": "2026-03-20",
            "end_date": "2026-03-20",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert [item["scene_identifier"] for item in body["items"]] == [
        "scene-in-range"
    ]


def test_list_scenes_is_paginated_and_ordered_newest_first(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        params={
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page_size"] == 1
    assert body["items"][0]["scene_identifier"] == "scene-late"


def test_list_scenes_rejects_reversed_date_range(scenes_client):
    client, _ = scenes_client

    response = client.get(
        f"/api/v1/lakes/{LAKE_ID}/scenes",
        params={
            "start_date": "2026-03-31",
            "end_date": "2026-03-01",
        },
    )

    assert response.status_code == 422


def test_list_scenes_requires_bounded_date_range(scenes_client):
    client, _ = scenes_client

    response = client.get(f"/api/v1/lakes/{LAKE_ID}/scenes")

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
    )

    assert response.status_code == 404
