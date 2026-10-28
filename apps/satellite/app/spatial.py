import math


class SpatialThresholdError(ValueError):
    """Excepción lanzada cuando la distancia supera el umbral permitido."""


# Radio volumétrico medio de la Tierra en metros (Estándar WGS84 / SRID 4326)
EARTH_RADIUS_M = 6371000.0


def calculate_wgs84_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia geodésica en metros entre dos puntos (SRID 4326)
    utilizando la fórmula de Haversine.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_M * c


def validate_spatial_pair(
    lat1: float, lon1: float, lat2: float, lon2: float, threshold_m: float
) -> float:
    """
    Evalúa un par de coordenadas y rechaza la operación si la distancia 
    supera el umbral. Retorna la distancia calculada si es válida.
    """
    distance = calculate_wgs84_distance(lat1, lon1, lat2, lon2)
    
    if distance > threshold_m:
        raise SpatialThresholdError(
            f"El par espacial excede el umbral: {distance:.2f}m > {threshold_m}m."
        )
        
    return distance
