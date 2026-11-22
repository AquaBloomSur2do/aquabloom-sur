from datetime import date, datetime, timedelta, timezone

import pytest

from apps.scientific.app.domains.execution.evaluation import (
    split_by_acquisition_date,
)


def test_split_keeps_acquisition_dates_in_chronological_partitions():
    records = [
        {"id": "early-a", "acquisition_date": "2026-01-01"},
        {"id": "late-a", "acquisition_date": "2026-01-03"},
        {"id": "early-b", "acquisition_date": "2026-01-01"},
        {"id": "middle", "acquisition_date": "2026-01-02"},
        {"id": "late-b", "acquisition_date": "2026-01-03"},
    ]

    split = split_by_acquisition_date(records, evaluation_fraction=0.2)

    assert split.strategy == "acquisition_date"
    assert split.cutoff_date == date(2026, 1, 3)
    assert split.rationale
    assert isinstance(split.rationale, str)
    assert {row["id"] for row in split.training} == {
        "early-a",
        "early-b",
        "middle",
    }
    assert {row["id"] for row in split.evaluation} == {"late-a", "late-b"}
    training_dates = {row["acquisition_date"] for row in split.training}
    evaluation_dates = {row["acquisition_date"] for row in split.evaluation}
    assert training_dates.isdisjoint(evaluation_dates)


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([], "No hay registros"),
        ([{"id": "1"}], "no contiene acquisition_date"),
        (
            [
                {"acquisition_date": "2026-01-01"},
                {"acquisition_date": "2026-01-01"},
            ],
            "al menos dos fechas",
        ),
        (
            [
                {"acquisition_date": "not-a-date"},
                {"acquisition_date": "2026-01-02"},
            ],
            "fecha de adquisición inválida",
        ),
    ],
)
def test_split_rejects_data_without_usable_dates(records, message):
    with pytest.raises(ValueError, match=message):
        split_by_acquisition_date(records, evaluation_fraction=0.2)


@pytest.mark.parametrize(
    "fraction",
    [0, 1, -0.1, 1.1, float("nan"), float("inf"), float("-inf")],
)
def test_split_rejects_invalid_evaluation_fraction(fraction):
    records = [
        {"acquisition_date": "2026-01-01"},
        {"acquisition_date": "2026-01-02"},
    ]

    with pytest.raises(ValueError, match="evaluation_fraction"):
        split_by_acquisition_date(records, evaluation_fraction=fraction)


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (" 2026-01-02T23:30:00Z ", date(2026, 1, 2)),
        ("2026-01-02T23:30:00-05:00", date(2026, 1, 3)),
        ("2026-01-02T23:30:00+14:00", date(2026, 1, 2)),
        (datetime(2026, 1, 2, 18, 30), date(2026, 1, 2)), # noqa: DTZ001
        (
            datetime(
                2026,
                1,
                2,
                23,
                30,
                tzinfo=timezone(timedelta(hours=-5)),
            ),
            date(2026, 1, 3),
        ),
    ],
)
def test_split_normalizes_iso_and_datetime_acquisition_values(timestamp, expected):
    records = [
        {"id": "early", "acquisition_date": "2026-01-01"},
        {"id": "target", "acquisition_date": timestamp},
        {"id": "late", "acquisition_date": "2026-01-03"},
    ]

    split = split_by_acquisition_date(records, evaluation_fraction=0.34)

    assert split.cutoff_date == expected
    assert split.rationale
    assert "target" in {row["id"] for row in split.evaluation}
