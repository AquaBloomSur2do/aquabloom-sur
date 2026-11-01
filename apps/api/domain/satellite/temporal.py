from collections.abc import Iterable
from datetime import datetime, timedelta

# Ventana temporal: Diferencia máxima en días entre la escena y la muestra in situ
MATCHUP_TEMPORAL_WINDOW_DAYS = 3

# Distancia Espacial: Radio máximo en metros
MATCHUP_SPATIAL_RADIUS_METERS = 50

# SRID Base de almacenamiento (WGS84)
MATCHUP_BASE_SRID = 4326

SCENE_PAIR_WINDOW = timedelta(days=5)
ScenePair = tuple[datetime, datetime]


def filter_scene_pairs(
    pairs: Iterable[ScenePair],
    *,
    window: timedelta = SCENE_PAIR_WINDOW,
) -> list[ScenePair]:
    """Keep pairs within the configured window (5 days by default)."""
    if window < timedelta(0):
        raise ValueError("La ventana temporal no puede ser negativa.")

    accepted_pairs = []
    for first_acquired_at, second_acquired_at in pairs:
        if (first_acquired_at.tzinfo is None) != (second_acquired_at.tzinfo is None):
            raise ValueError(
                "Las fechas del par deben usar ambas zona horaria o ninguna."
            )
        if abs(first_acquired_at - second_acquired_at) <= window:
            accepted_pairs.append((first_acquired_at, second_acquired_at))

    return accepted_pairs
