from uuid import uuid4

import pytest
from catalog.application.schemas import StationCreate
from pydantic import ValidationError


def test_estacion_coordenadas_validas():
    # Debe pasar sin errores
    estacion = StationCreate(
        lake_id=uuid4(),
        code="VILL-01",
        name="Estación Villarrica Centro",
        latitude=-39.28,
        longitude=-72.22,
        source="DGA",
        activity="Monitoreo activo",
    )
    assert estacion.latitude == -39.28


def test_estacion_rechaza_latitud_invalida():
    # Latitud fuera de [-90, 90] debe lanzar ValidationError
    with pytest.raises(ValidationError) as error_info:
        StationCreate(
            lake_id=uuid4(),
            name="Estación Error",
            latitude=-91.0,  # ¡Inválido!
            longitude=-72.0,
            source="DGA",
            activity="Monitoreo",
        )
    assert "latitude" in str(error_info.value)


def test_estacion_rechaza_longitud_invalida():
    # Longitud fuera de [-180, 180] debe lanzar ValidationError
    with pytest.raises(ValidationError) as error_info:
        StationCreate(
            lake_id=uuid4(),
            name="Estación Error",
            latitude=-39.0,
            longitude=181.5,  # ¡Inválido!
            source="DGA",
            activity="Monitoreo",
        )
    assert "longitude" in str(error_info.value)
