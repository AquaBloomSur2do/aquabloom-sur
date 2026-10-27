from datetime import UTC, datetime, timedelta

import pytest

from domain.satellite.temporal import SCENE_PAIR_WINDOW, filter_scene_pairs


def test_filter_scene_pairs_accepts_pairs_inside_and_on_window_boundary():
    first = datetime(2026, 10, 1, tzinfo=UTC)
    inside_window = (first, first + timedelta(days=4))
    on_boundary = (first, first + SCENE_PAIR_WINDOW)

    assert filter_scene_pairs([inside_window, on_boundary]) == [
        inside_window,
        on_boundary,
    ]


def test_filter_scene_pairs_excludes_pairs_outside_window():
    first = datetime(2026, 10, 1, tzinfo=UTC)
    accepted = (first, first + timedelta(days=5))
    excluded = (first, first + timedelta(days=6))

    assert filter_scene_pairs([accepted, excluded]) == [accepted]


def test_filter_scene_pairs_uses_absolute_time_difference():
    first = datetime(2026, 10, 10, tzinfo=UTC)
    second = datetime(2026, 10, 5, tzinfo=UTC)

    assert filter_scene_pairs([(first, second)]) == [(first, second)]


def test_filter_scene_pairs_rejects_negative_window():
    with pytest.raises(ValueError, match="no puede ser negativa"):
        filter_scene_pairs([], window=timedelta(days=-1))


def test_filter_scene_pairs_rejects_mixed_timezone_awareness():
    aware = datetime(2026, 10, 1, tzinfo=UTC)
    naive = datetime.fromisoformat("2026-10-02")

    with pytest.raises(ValueError, match="zona horaria"):
        filter_scene_pairs([(aware, naive)])
