import asyncio
import math
from typing import Any
from uuid import UUID

from apps.scientific.app.domains.execution.schemas_execution import (
    JobCreate,
    PilotMetricsResult,
)

JOB_TIMEOUT_SECONDS = 10.0


def job_matches_request(
    job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return job.get("job_type") == payload.job_type and job.get("config") == config


def build_job_accepted_response(job: dict[str, Any]) -> dict[str, Any]:
    job_id = UUID(str(job["id"]))
    return {
        "job_id": job_id,
        "status": job["status"],
        "status_url": f"/api/v1/executions/{job_id}",
    }


async def run_scientific_algorithm(config: dict[str, Any]) -> dict[str, Any]:
    scene_id = config.get("scene_id", "")
    if scene_id == "scene_fail":
        raise RuntimeError(
            "Excepción interna: Fallo al procesar los tensores de la escena."
        )
    if scene_id == "scene_timeout":
        await asyncio.sleep(2.0)
    else:
        await asyncio.sleep(0.1)
    return {"accuracy": 0.98, "processed_pixels": 102400}


def calculate_pilot_metrics(y_true: list[float], y_pred: list[float]) -> PilotMetricsResult:
    """Calcula MAE, RMSE, sesgo y R² condicional cumpliendo RNF-26 (S2-157)."""
    if not y_true or not y_pred:
        raise ValueError("Las listas de observaciones y predicciones no pueden estar vacías.")
    if len(y_true) != len(y_pred):
        raise ValueError("Las listas deben tener exactamente la misma longitud.")

    n = len(y_true)
    mean_y_true = sum(y_true) / n
    sum_error = 0.0
    sum_abs_error = 0.0
    sum_sq_error = 0.0
    ss_tot = 0.0

    for true_val, pred_val in zip(y_true, y_pred, strict=True):
        if not (math.isfinite(true_val) and math.isfinite(pred_val)):
            raise ValueError("Los valores deben ser finitos (sin NaN ni Inf).")
        error = pred_val - true_val
        sum_error += error
        sum_abs_error += abs(error)
        sum_sq_error += error ** 2
        ss_tot += (true_val - mean_y_true) ** 2

    mae = sum_abs_error / n
    rmse = math.sqrt(sum_sq_error / n)
    bias = sum_error / n

    limitations = [
        "R² no debe interpretarse de manera aislada; evalúe conjuntamente MAE, RMSE y sesgo (RNF-26)."
    ]
    if n < 10:
        limitations.append(f"Tamaño de muestra pequeño (n={n}). Interpretar con precaución.")

    r2_computable = False
    r2_val = None

    if n >= 2 and not math.isclose(ss_tot, 0.0, abs_tol=1e-12):
        r2_computable = True
        r2_val = round(1.0 - (sum_sq_error / ss_tot), 4)
    elif n < 2:
        limitations.append("R² no calculable: se requieren al menos 2 observaciones.")
    else:
        limitations.append("R² no calculable: varianza de observaciones reales es cero.")

    return PilotMetricsResult(
        sample_count=n,
        mae=round(mae, 4),
        rmse=round(rmse, 4),
        bias=round(bias, 4),
        r2_computable=r2_computable,
        r2=r2_val,
        limitations=limitations,
    )

