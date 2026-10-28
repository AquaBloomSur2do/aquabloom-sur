import pytest
from app.spatial import SpatialThresholdError, validate_spatial_pair


def test_validate_spatial_pair_within_threshold():
    # Coordenadas cercanas (ej. dos puntos en el mismo lago)
    lat1, lon1 = -39.2700, -72.1300
    lat2, lon2 = -39.2750, -72.1300
    threshold = 1000.0  # 1000 metros (1 km)
    
    distance = validate_spatial_pair(lat1, lon1, lat2, lon2, threshold)
    
    assert distance < threshold
    assert distance > 0.0


def test_validate_spatial_pair_exceeds_threshold():
    # Coordenadas distantes (ej. Lago Villarrica a Lago Calafquén)
    lat1, lon1 = -39.2700, -72.1300
    lat2, lon2 = -39.5400, -72.1400
    threshold = 1000.0  # 1000 metros (1 km)
    
    with pytest.raises(SpatialThresholdError) as excinfo:
        validate_spatial_pair(lat1, lon1, lat2, lon2, threshold)
        
    assert "excede el umbral" in str(excinfo.value)
