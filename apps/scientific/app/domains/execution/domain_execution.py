import csv
import hashlib
import io
import math
from collections.abc import Hashable, Iterable
from typing import Any

from apps.scientific.app.domains.execution.schemas_execution import (
    BaselineInfo,
    EstimationRequestInput,
    JobCreate,
    ModelScopeSpec,
    PilotMetricsResult,
    ScientificJobStatusEnum,
    TrainingMetrics,
    TrainingResult,
    ValidatedEstimationInput,
)

JOB_TIMEOUT_SECONDS = 10.0
MAX_ERROR_MESSAGE_LENGTH = 1000
DEFAULT_JOB_ERROR_MESSAGE = (
    "Error interno durante la ejecución del trabajo científico."
)


class JobLimitExceededError(RuntimeError):
    """Error determinista cuando un trabajo excede un límite operativo permitido."""


def resolve_job_timeout(timeout_seconds: float | None) -> float:
    """Valida y resuelve el tiempo máximo permitido para un trabajo científico."""
    resolved = JOB_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    if not isinstance(resolved, (int, float)) or isinstance(resolved, bool):
        raise TypeError("El tiempo máximo de ejecución debe ser numérico.")
    if not math.isfinite(resolved) or resolved <= 0:
        raise ValueError(
            "El tiempo máximo de ejecución debe ser un número finito mayor a 0."
        )
    return float(resolved)


def sanitize_error_message(
    message: str | None,
    *,
    fallback: str = DEFAULT_JOB_ERROR_MESSAGE,
    max_length: int = MAX_ERROR_MESSAGE_LENGTH,
) -> str:
    """Normaliza espacios, garantiza texto no vacío y acota el largo del error."""
    normalized = " ".join((message or "").split())
    if not normalized:
        normalized = fallback
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[: max_length - 3].rstrip()}..."


def build_timeout_error_message(timeout_seconds: float) -> str:
    return sanitize_error_message(
        f"Tiempo máximo de ejecución excedido (Timeout de {timeout_seconds}s)."
    )


def format_limit_exceeded_error_message(exc: JobLimitExceededError) -> str:
    detail = str(exc).strip()
    if not detail:
        return "Límite operativo de ejecución excedido."
    if detail.lower().startswith("límite"):
        return sanitize_error_message(detail)
    return sanitize_error_message(f"Límite de ejecución excedido: {detail}")


def format_exception_error_message(exc: Exception) -> str:
    detail = str(exc).strip()
    if not detail:
        return sanitize_error_message(
            f"Error inesperado ({type(exc).__name__}) durante la ejecución del trabajo científico."
        )
    return sanitize_error_message(detail)


def build_running_update_payload(started_at: str) -> dict[str, Any]:
    return {
        "status": "running",
        "started_at": started_at,
    }


def build_completed_update_payload(
    result: dict[str, Any], completed_at: str
) -> dict[str, Any]:
    return {
        "status": "completed",
        "result": result,
        "error_message": None,
        "completed_at": completed_at,
    }


def build_failure_update_payload(
    error_message: str, completed_at: str
) -> dict[str, Any]:
    return {
        "status": "failed",
        "result": None,
        "error_message": sanitize_error_message(error_message),
        "completed_at": completed_at,
    }


def parse_training_csv(file_bytes: bytes, expected_checksum: str) -> list[dict[str, Any]]:
    """Verifica y convierte el CSV de entrenamiento en filas numéricas."""
    if not file_bytes:
        raise ValueError("El archivo CSV está vacío.")

    actual_checksum = hashlib.sha256(file_bytes).hexdigest()
    if actual_checksum != expected_checksum:
        raise ValueError("Checksum del archivo de entrenamiento incorrecto.")

    try:
        csv_text = file_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("El archivo de entrenamiento no está codificado en UTF-8.") from exc

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or "clorofila_a" not in reader.fieldnames:
        raise ValueError("El archivo CSV no contiene la columna objetivo 'clorofila_a'.")

    rows = list(reader)
    if not rows:
        raise ValueError("El archivo CSV está vacío.")

    validated_rows: list[dict[str, Any]] = []
    for row in rows:
        value = row.get("clorofila_a")
        if value is None or value.strip() == "":
            raise ValueError("Valor faltante en la columna 'clorofila_a'.")
        try:
            target = float(value)
        except ValueError as exc:
            raise ValueError(
                f"Valor no numérico o inválido en 'clorofila_a': {value}"
            ) from exc
        if not math.isfinite(target):
            raise ValueError(
                f"Valor no numérico o inválido en 'clorofila_a': {value}"
            )
        row["clorofila_a"] = target
        validated_rows.append(row)

    return validated_rows


def split_training_validation(
    data: list[dict[str, Any]], split_ratio: float = 0.8
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Divide secuencialmente los datos y reserva observaciones para evaluación."""
    if not math.isfinite(split_ratio) or not 0 < split_ratio < 1:
        raise ValueError("La proporción de entrenamiento debe estar entre 0 y 1.")
    if len(data) < 2:
        raise ValueError("Se requieren al menos 2 observaciones para evaluar el modelo.")

    train_size = max(1, int(len(data) * split_ratio))
    if train_size == len(data):
        train_size = len(data) - 1
    return data[:train_size], data[train_size:]


def calculate_baseline(
    train_data: list[dict[str, Any]],
    val_data: list[dict[str, Any]],
    version: str | None = None,
    dataset_version_id: str | None = None,
    model_version_id: str | None = None,
) -> dict[str, Any]:
    if not train_data:
        raise ValueError("Conjunto de entrenamiento vacío. Imposible calcular baseline.")
    if not val_data:
        raise ValueError("Conjunto de evaluación vacío. Imposible calcular métricas.")

    train_targets = [row["clorofila_a"] for row in train_data]
    prediction_value = sum(train_targets) / len(train_targets)
    val_targets = [row["clorofila_a"] for row in val_data]
    predictions = [prediction_value] * len(val_data)
    mae = sum(
        abs(actual - prediction)
        for actual, prediction in zip(val_targets, predictions, strict=True)
    ) / len(val_targets)
    rmse = math.sqrt(
        sum(
            (actual - prediction) ** 2
            for actual, prediction in zip(val_targets, predictions, strict=True)
        )
        / len(val_targets)
    )

    resolved_version = version or model_version_id or dataset_version_id
    warnings = [
        "Modelo baseline de referencia basado en la media de clorofila_a de entrenamiento; no incorpora variables espectrales ni espaciales."
    ]
    if len(train_data) < 10 or len(val_data) < 5:
        warnings.append(
            f"Tamaño de muestra reducido (entrenamiento={len(train_data)}, validación={len(val_data)}); interpretar métricas con precaución."
        )
    if not resolved_version:
        warnings.append(
            "Versión de dataset o modelo no informada durante la ejecución del baseline."
        )

    result = TrainingResult(
        model="baseline",
        baseline=BaselineInfo(
            strategy="mean_clorofila_a",
            target_variable="clorofila_a",
            prediction_value=prediction_value,
            train_sample_count=len(train_data),
            validation_sample_count=len(val_data),
        ),
        prediction_value=prediction_value,
        predictions=predictions,
        metrics=TrainingMetrics(mae=mae, rmse=rmse),
        version=resolved_version,
        dataset_version_id=dataset_version_id,
        model_version_id=model_version_id,
        status=ScientificJobStatusEnum.COMPLETED,
        warnings=warnings,
    )
    return result.model_dump(mode="json")

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
        raise EstimationInputValidationError(
            "La solicitud de estimación no contiene observaciones espectrales."
        )

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

        if (
            not math.isfinite(obs.index_value)
            or obs.index_value < -1.0
            or obs.index_value > 1.0
        ):
            raise EstimationInputValidationError(
                f"El valor del índice ({obs.index_value}) en la observación {obs.observation_id} está fuera del dominio físico [-1.0, 1.0]."
            )

        if (
            obs.index_value < model_spec.min_index_value
            or obs.index_value > model_spec.max_index_value
        ):
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


def calculate_pilot_metrics(
    y_true: list[float], y_pred: list[float]
) -> PilotMetricsResult:
    """Calcula MAE, RMSE, sesgo y R² condicional cumpliendo RNF-26 (S2-157)."""
    if not y_true or not y_pred:
        raise ValueError(
            "Las listas de observaciones y predicciones no pueden estar vacías."
        )
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
        sum_sq_error += error**2
        ss_tot += (true_val - mean_y_true) ** 2

    mae = sum_abs_error / n
    rmse = math.sqrt(sum_sq_error / n)
    bias = sum_error / n

    limitations = [
        "R² no debe interpretarse de manera aislada; evalúe conjuntamente MAE, RMSE y sesgo (RNF-26)."
    ]
    if n < 10:
        limitations.append(
            f"Tamaño de muestra pequeño (n={n}). Interpretar con precaución."
        )

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




