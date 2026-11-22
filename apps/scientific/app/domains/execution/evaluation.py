"""Domain utilities for temporal evaluation partitions.

The pilot's scene and observation schemas expose an acquisition date but do not
provide campaign identifiers that would support grouping observations by campaign.
This module therefore partitions on acquisition_date. A random partition is not
used because it can place observations from later periods in training or earlier
periods in evaluation, causing temporal data leakage. Applying evaluation_fraction
to the ordered list of unique dates keeps every acquisition date atomic: all
observations from a date remain in the same partition.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import ceil, isfinite
from typing import Literal


@dataclass(frozen=True)
class DateEvaluationPartition:
    strategy: Literal["acquisition_date"]
    training: tuple[Mapping[str, object], ...]
    evaluation: tuple[Mapping[str, object], ...]
    cutoff_date: date
    rationale: str


def _parse_acquisition_date(value: object, row_number: int) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).date()
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        try:
            return date.fromisoformat(normalized)
        except ValueError:
            try:
                timestamp = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
                if timestamp.tzinfo is not None:
                    return timestamp.astimezone(timezone.utc).date()
                return timestamp.date()
            except ValueError as exc:
                raise ValueError(
                    f"El registro {row_number} tiene una fecha de adquisición inválida."
                ) from exc
    raise ValueError(
        f"El registro {row_number} no contiene una fecha de adquisición válida."
    )


def split_by_acquisition_date(
    records: Sequence[Mapping[str, object]],
    evaluation_fraction: float,
) -> DateEvaluationPartition:
    """Create chronological, future-dated training and evaluation partitions.

    Random splitting is rejected as a design choice because it leaks temporal
    information: observations from later dates could affect training when earlier
    dates are evaluated. acquisition_date is used because the current pilot scene
    and observation schema attributes expose it directly, while no campaign
    attribute is available for campaign-based grouping. evaluation_fraction is
    applied to unique acquisition dates, not individual records, so that each date
    is atomic and no date is split between training and evaluation.
    """
    if not isfinite(evaluation_fraction) or not 0 < evaluation_fraction < 1:
        raise ValueError("evaluation_fraction debe estar entre 0 y 1.")
    if not records:
        raise ValueError("No hay registros para crear la partición de evaluación.")

    records_by_date: dict[date, list[Mapping[str, object]]] = {}
    for row_number, record in enumerate(records, start=1):
        if "acquisition_date" not in record:
            raise ValueError(
                f"El registro {row_number} no contiene acquisition_date; "
                "no se puede crear una partición temporal."
            )
        acquisition_date = _parse_acquisition_date(
            record["acquisition_date"], row_number
        )
        records_by_date.setdefault(acquisition_date, []).append(record)

    ordered_dates = sorted(records_by_date)
    if len(ordered_dates) < 2:
        raise ValueError(
            "Se requieren al menos dos fechas de adquisición distintas "
            "para separar entrenamiento y evaluación."
        )

    evaluation_date_count = min(
        len(ordered_dates) - 1,
        max(1, ceil(len(ordered_dates) * evaluation_fraction)),
    )
    cutoff_date = ordered_dates[-evaluation_date_count]
    training_records = tuple(
        record
        for acquisition_date in ordered_dates
        if acquisition_date < cutoff_date
        for record in records_by_date[acquisition_date]
    )
    evaluation_records = tuple(
        record
        for acquisition_date in ordered_dates
        if acquisition_date >= cutoff_date
        for record in records_by_date[acquisition_date]
    )

    rationale = (
        "Se descarta una partición aleatoria para evitar fuga temporal; "
        "acquisition_date se usa porque es el atributo temporal disponible en el "
        "esquema del piloto y no existe agrupación por campaña. "
        "evaluation_fraction se aplica sobre fechas únicas para mantener cada "
        "fecha atómica."
    )
    return DateEvaluationPartition(
        strategy="acquisition_date",
        training=training_records,
        evaluation=evaluation_records,
        cutoff_date=cutoff_date,
        rationale=rationale,
    )
