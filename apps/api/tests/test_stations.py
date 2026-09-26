import pytest

from app.services import validate_station_inside_lake


def test_validate_station_inside_lake():
    # Polígono Mockun cuadrado de 10x10
    mock_lake_geojson = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]]
    }
    
    # Criterio: Acepta un punto contenido
    validate_station_inside_lake(mock_lake_geojson, lat=5.0, lon=5.0)
    
    # Criterio: Rechaza con ValueError (que la API traduce a 422) un punto fuera
    with pytest.raises(ValueError, match="fuera del polígono"):
        validate_station_inside_lake(mock_lake_geojson, lat=15.0, lon=15.0)