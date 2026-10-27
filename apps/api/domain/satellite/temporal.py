from collections.abc import Iterable
from datetime import datetime, timedelta

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
