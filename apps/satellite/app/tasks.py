from math import fsum


def summarize_measurements(measurements: list[float]) -> dict[str, int | float]:
    if not measurements:
        raise ValueError("Se requiere al menos una medición.")

    return {
        "count": len(measurements),
        "minimum": min(measurements),
        "maximum": max(measurements),
        "mean": fsum(value / len(measurements) for value in measurements),
    }
