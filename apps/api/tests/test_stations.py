import os
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-service-key")

from app.services import validate_station_inside_lake
from catalog.application.endpoints import create_station
from catalog.application.schemas import StationCreate


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self._filters = {}
        self._insert_payload = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, field, value):
        self._filters[field] = value
        return self

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def execute(self):
        table_items = self.db.tables.setdefault(self.table_name, [])
        items = list(table_items)

        for field, value in self._filters.items():
            items = [item for item in items if str(item.get(field)) == str(value)]

        if self._insert_payload is not None:
            payload = {**self._insert_payload, "id": str(uuid.uuid4())}
            table_items.append(payload)
            return FakeResponse([payload])

        return FakeResponse(items)


class FakeSupabase:
    def __init__(self, lake_geom=None, stations=None):
        self.tables = {
            "lakes": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "geom": lake_geom
                    or {"type": "Polygon", "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]]},
                }
            ],
            "stations": stations or [],
        }

    def table(self, table_name):
        return FakeTable(self, table_name)


def test_validate_station_inside_lake():
    mock_lake_geojson = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]],
    }

    validate_station_inside_lake(mock_lake_geojson, lat=5.0, lon=5.0)

    with pytest.raises(ValueError, match="fuera del polígono"):
        validate_station_inside_lake(mock_lake_geojson, lat=15.0, lon=15.0)


def test_crear_estacion_codigo_duplicado(monkeypatch):
    lake_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    fake_db = FakeSupabase(
        stations=[{"lake_id": str(lake_id), "code": "ST-001", "name": "Existente"}]
    )
    monkeypatch.setattr("catalog.application.endpoints.supabase", fake_db)

    payload = StationCreate(
        code="ST-001",
        name="Nueva",
        latitude=5.0,
        longitude=5.0,
    )

    with pytest.raises(HTTPException) as exc_info:
        create_station(lake_id, payload)

    assert exc_info.value.status_code == 409
    assert "ya existe" in str(exc_info.value.detail).lower()
    assert len(fake_db.tables["stations"]) == 1


def test_crear_estacion_coordenadas_fuera_de_rango():
    with pytest.raises(ValidationError):
        StationCreate(
            code="ST-002",
            name="Fuera de rango",
            latitude=91.0,
            longitude=0.0,
        )


def test_crear_estacion_punto_fuera_del_lago(monkeypatch):
    lake_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    fake_db = FakeSupabase()
    monkeypatch.setattr("catalog.application.endpoints.supabase", fake_db)

    payload = StationCreate(
        code="ST-003",
        name="Fuera del lago",
        latitude=15.0,
        longitude=15.0,
    )

    with pytest.raises(HTTPException) as exc_info:
        create_station(lake_id, payload)

    assert exc_info.value.status_code == 422
    assert "fuera del polígono" in str(exc_info.value.detail).lower()
    assert len(fake_db.tables["stations"]) == 0