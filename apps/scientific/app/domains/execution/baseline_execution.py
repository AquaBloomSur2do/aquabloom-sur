import math
from typing import Any


def calculate_baseline(
    train_data: list[dict[str, Any]], val_data: list[dict[str, Any]]
) -> dict[str, Any]:
    
    if not train_data:
        raise ValueError("Conjunto de entrenamiento vacío. Imposible calcular baseline.")
    if not val_data:
        raise ValueError("Conjunto de evaluación vacío. Imposible calcular métricas.")

    train_targets = [row["clorofila_a"] for row in train_data]
    baseline_value = sum(train_targets) / len(train_targets)

    val_targets = [row["clorofila_a"] for row in val_data]
    predictions = [baseline_value for _ in val_data]

    mae = sum(abs(t - p) for t, p in zip(val_targets, predictions, strict=False)) / len(val_targets)
    rmse = math.sqrt(
        sum((t - p) ** 2 for t, p in zip(val_targets, predictions, strict=False))
        / len(val_targets)
    )

    return {
        "model": "baseline",
        "prediction_value": baseline_value,
        "metrics": {"mae": mae, "rmse": rmse},
        "predictions": predictions,
    }
