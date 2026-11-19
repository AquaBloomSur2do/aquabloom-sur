import asyncio
import math
from collections.abc import Hashable, Iterable
from typing import Any

from apps.scientific.app.domains.execution.baseline_execution import calculate_baseline
from apps.scientific.app.domains.execution.data_execution import (
    fetch_training_data,
    split_training_validation,
)
from apps.scientific.app.domains.execution.schemas_execution import JobCreate

JOB_TIMEOUT_SECONDS = 300
from apps.scientific.app.domains.execution.schemas_execution import (
    EstimationRequestInput,
    JobCreate,
    ModelScopeSpec,
    PilotMetricsResult,
    ValidatedEstimationInput,
)

JOB_TIMEOUT_SECONDS = 10.0


def validate_group_partition_disjointness(
    training_groups: Iterable[Hashable],
    evaluation_groups: Iterable[Hashable],
) -> None:
    """Rechaza particiones que compartan grupos entre entrenamiento y evaluación."""
    overlap = set(training_groups).intersection(evaluation_groups)
    if overlap:
        groups = ", ".join(sorted(map(repr, overlap)))
        raise ValueError(
            f"Fuga de datos: grupos compartidos entre entrenamiento y evaluación: {groups}."
        )


def job_matches_request(
    job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return job.get("job_type") == payload.job_type and job.get("config") == config


def build_job_accepted_response(job: dict[str, Any]) -> dict[str, Any]:
    job_id = job.get("id") or job.get("job_id")
    return {
        "job_id": str(job_id),
        "status": job.get("status", "queued"),
        "message": "Trabajo encolado y en procesamiento.",
        "status_url": f"/api/v1/executions/{job_id}",
    }

def job_matches_request(
    existing_job: dict[str, Any], payload: JobCreate, config: dict[str, Any]
) -> bool:
    return (
        existing_job.get("job_type") == payload.job_type
        and existing_job.get("config") == config
    )


async def run_scientific_algorithm(
    job_type: str, config: dict[str, Any]
) -> dict[str, Any]:
    """Ejecuta el algoritmo científico real (baseline para S2-155)."""
    await asyncio.sleep(1)

    if job_type != "training":
        return {"message": f"Tipo de trabajo '{job_type}' no implementado aún."}

    dataset_id = config.get("dataset_id")
    version_id = config.get("version_id")

    if not dataset_id or not version_id:
        raise ValueError("Faltan dataset_id o version_id en la configuración.")

    # 1. Cargar datos de entrenamiento desde el storage
    raw_data = fetch_training_data(str(dataset_id), str(version_id))
    
    # 2. Separar particiones (80% entrenamiento, 20% validación)
    train_data, val_data = split_training_validation(raw_data, split_ratio=0.8)
    
    # 3. Calcular baseline exclusivo sobre entrenamiento y validar
    result = calculate_baseline(train_data, val_data)

    return result

PILOT_ALLOWED_VARIABLES = {"chlorophyll_a": "chlorophyll_a", "clorofila_a": "chlorophyll_a"}
PILOT_ALLOWED_UNITS = {"ug/l": "ug/L", "µg/l": "ug/L", "μg/l": "ug/L", "mg/m3": "mg/m3"}
PILOT_ALLOWED_INDICES = {"ndci": "NDCI"}
INVALID_QUALITY_FLAGS = {"CLOUDY", "INVALID", "MASKED", "QUARANTINED", "REJECTED"}


class EstimationInputValidationError(ValueError):
    """Error determinista cuando el modelo o las observaciones son incompatibles para estimación."""


def _normalize_variable(value: str) -> str:
    key = value.strip().lower()
    if key not in PILOT_ALLOWED_VARIABLES:
        raise EstimationInputValidationError(
            f"Variable objetivo incompatible '{value}'. El piloto solo admite chlorophyll_a / clorofila_a."
        )
    return PILOT_ALLOWED_VARIABLES[key]


def _normalize_unit(value: str) -> str:
    key = value.strip().lower()
    if key not in PILOT_ALLOWED_UNITS:
        raise EstimationInputValidationError(
            f"Unidad incompatible '{value}'. Unidades admitidas: ug/L o mg/m3."
        )
    return PILOT_ALLOWED_UNITS[key]


def _normalize_index(value: str) -> str:
    key = value.strip().lower()
    if key not in PILOT_ALLOWED_INDICES:
        raise EstimationInputValidationError(
            f"Índice espectral incompatible '{value}'. El alcance piloto exige NDCI."
        )
    return PILOT_ALLOWED_INDICES[key]


def validate_estimation_inputs(
    model_spec: ModelScopeSpec,
    request: EstimationRequestInput,
) -> ValidatedEstimationInput:
    """
    Valida que el modelo y las observaciones espectrales sean compatibles (S2-169 / RN-06, RN-07, RN-08).
    Rechaza variable, unidad, lago, calidad o índice incompatibles antes de ejecutar la inferencia.
    """
    model_status = model_spec.status.strip().upper()
    if model_status in {"DEPRECATED", "REJECTED", "ARCHIVED", "DRAFT"}:
        raise EstimationInputValidationError(
            f"El modelo {model_spec.model_version_id} se encuentra en estado '{model_status}' y no puede usarse para estimación."
        )

    if model_spec.lake_id != request.lake_id:
        raise EstimationInputValidationError(
            f"Incompatibilidad geográfica: el modelo pertenece al lago {model_spec.lake_id}, pero la solicitud es para el lago {request.lake_id}."
        )

    req_variable = _normalize_variable(request.target_variable)
    mod_variable = _normalize_variable(model_spec.target_variable)
    if req_variable != mod_variable:
        raise EstimationInputValidationError(
            f"Variable solicitada ({req_variable}) incompatible con la variable del modelo ({mod_variable})."
        )

    req_unit = _normalize_unit(request.unit)
    mod_unit = _normalize_unit(model_spec.unit)
    if req_unit != mod_unit:
        raise EstimationInputValidationError(
            f"Unidad solicitada ({req_unit}) incompatible con la unidad del modelo ({mod_unit})."
        )

    req_index = _normalize_index(request.required_index)
    mod_index = _normalize_index(model_spec.required_index)
    if req_index != mod_index:
        raise EstimationInputValidationError(
            f"Índice solicitado ({req_index}) incompatible con el índice requerido por el modelo ({mod_index})."
        )

    if not request.observations:
        raise EstimationInputValidationError("La solicitud de estimación no contiene observaciones espectrales.")

    warnings: list[str] = []
    if model_status == "EXPERIMENTAL":
        warnings.append(
            "El modelo se encuentra en condición EXPERIMENTAL; los resultados son preliminares y requieren validación local."
        )

    extrapolated_count = 0
    for obs in request.observations:
        if obs.lake_id != request.lake_id:
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} pertenece a otro lago ({obs.lake_id} != {request.lake_id})."
            )
        if obs.scene_id != request.scene_id:
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} pertenece a otra escena ({obs.scene_id} != {request.scene_id})."
            )

        obs_index = _normalize_index(obs.spectral_index)
        if obs_index != mod_index:
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} posee índice '{obs.spectral_index}', incompatible con '{mod_index}'."
            )

        quality_flag = obs.quality.strip().upper()
        if quality_flag in INVALID_QUALITY_FLAGS or quality_flag != "VALID":
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} tiene bandera de calidad inválida ('{obs.quality}')."
            )

        if not math.isfinite(obs.index_value) or obs.index_value < -1.0 or obs.index_value > 1.0:
            raise EstimationInputValidationError(
                f"El valor del índice ({obs.index_value}) en la observación {obs.observation_id} está fuera del dominio físico [-1.0, 1.0]."
            )

        if obs.index_value < model_spec.min_index_value or obs.index_value > model_spec.max_index_value:
            extrapolated_count += 1

    if extrapolated_count > 0:
        warnings.append(
            f"Se detectaron {extrapolated_count} observaciones fuera del rango de entrenamiento [{model_spec.min_index_value}, {model_spec.max_index_value}] (extrapolación)."
        )

    return ValidatedEstimationInput(
        model_version_id=model_spec.model_version_id,
        lake_id=request.lake_id,
        scene_id=request.scene_id,
        target_variable=mod_variable,
        unit=mod_unit,
        required_index=mod_index,
        valid_observation_count=len(request.observations),
        warnings=warnings,
    )

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
