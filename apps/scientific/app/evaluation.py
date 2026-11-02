from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from math import ceil, isfinite
from typing import Literal


@dataclass(frozen=True)
class DateEvaluationPartition:
    strategy: Literal["acquisition_date"]
    training: tuple[Mapping[str, object], ...]
    evaluation: tuple[Mapping[str, object], ...]
    cutoff_date: date


def _parse_acquisition_date(value: object, row_number: int) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
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
    """Keep every acquisition date in exactly one chronological partition."""
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

    return DateEvaluationPartition(
        strategy="acquisition_date",
        training=training_records,
        evaluation=evaluation_records,
        cutoff_date=cutoff_date,
    )
