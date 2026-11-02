from datetime import date

import pytest
from app.evaluation import split_by_acquisition_date


def test_split_keeps_each_acquisition_date_in_one_chronological_partition():
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
    assert {row["id"] for row in split.training} == {
        "early-a",
        "early-b",
        "middle",
    }
    assert {row["id"] for row in split.evaluation} == {"late-a", "late-b"}
    assert {
        row["acquisition_date"] for row in split.training
    }.isdisjoint({row["acquisition_date"] for row in split.evaluation})


@pytest.mark.parametrize(
    ("records", "fraction", "message"),
    [
        ([], 0.2, "No hay registros"),
        ([{"id": "1"}], 0.2, "no contiene acquisition_date"),
        (
            [
                {"acquisition_date": "2026-01-01"},
                {"acquisition_date": "2026-01-01"},
            ],
            0.2,
            "al menos dos fechas",
        ),
        (
            [
                {"acquisition_date": "not-a-date"},
                {"acquisition_date": "2026-01-02"},
            ],
            0.2,
            "fecha de adquisición inválida",
        ),
    ],
)
def test_split_rejects_data_without_usable_dates(records, fraction, message):
    with pytest.raises(ValueError, match=message):
        split_by_acquisition_date(records, evaluation_fraction=fraction)


@pytest.mark.parametrize("fraction", [0, 1, -0.1, 1.1])
def test_split_rejects_invalid_evaluation_fraction(fraction):
    records = [
        {"acquisition_date": "2026-01-01"},
        {"acquisition_date": "2026-01-02"},
    ]

    with pytest.raises(ValueError, match="evaluation_fraction"):
        split_by_acquisition_date(records, evaluation_fraction=fraction)
