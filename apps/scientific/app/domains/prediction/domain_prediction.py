import math
from typing import Any
from uuid import UUID

from apps.scientific.app.core.permissions import CATALOG_ACTIONS, has_permission
from apps.scientific.app.domains.prediction.schemas_prediction import (
    AppliedRule,
    EstimationPoint,
    EstimationProvenance,
    PredictionDetailResponse,
)

ALLOWED_PREDICTION_READ_ROLES = frozenset(
    {"admin", "administrador", "supervisor", "investigador", "auditor"}
)
PREDICTION_READ_PERMISSION = "predictions:read"

KNOWN_VARIABLE_KEYS = (
    "chlorophyll_a",
    "clorofila_a",
    "turbidity",
    "turbidez",
    "temperature",
    "temperatura",
)


def has_prediction_read_permission(
    membership: dict[str, Any] | None,
    user_payload: dict[str, Any] | None,
) -> bool:
    """Verifica rol reconocido en la organización o permiso explícito de lectura."""
    if not membership:
        return False

    membership_role = str(membership.get("role") or "").strip().lower()
    if membership_role in ALLOWED_PREDICTION_READ_ROLES:
        return True

    return has_permission(user_payload, PREDICTION_READ_PERMISSION) or has_permission(
        user_payload, CATALOG_ACTIONS["READ"]
    )


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _to_optional_float(value: Any) -> float | None:
    if _is_finite_number(value):
        return float(value)
    return None


def _to_optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _resolve_variable(result: dict[str, Any]) -> str:
    for key in ("variable", "target_variable"):
        raw = result.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

    for key in KNOWN_VARIABLE_KEYS:
        if key in result and _is_finite_number(result[key]):
            return key

    return "unknown"


def _resolve_unit(result: dict[str, Any], variable: str) -> str:
    for key in ("unit", "unidad"):
        raw = result.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

    if variable.lower() in {"chlorophyll_a", "clorofila_a"}:
        return "ug/L"
    return "unknown"


def _resolve_status(result: dict[str, Any]) -> str:
    for key in ("status", "estado"):
        raw = result.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower()
    return "completed"


def _parse_point_dict(raw_point: dict[str, Any], index: int) -> EstimationPoint | None:
    value = raw_point.get("value")
    if value is None:
        value = raw_point.get("prediction_value")
    if not _is_finite_number(value):
        return None

    latitude = _to_optional_float(
        raw_point.get("latitude")
        if raw_point.get("latitude") is not None
        else raw_point.get("lat")
    )
    longitude = _to_optional_float(
        raw_point.get("longitude")
        if raw_point.get("longitude") is not None
        else (
            raw_point.get("lng")
            if raw_point.get("lng") is not None
            else raw_point.get("lon")
        )
    )

    raw_point_id = raw_point.get("point_id") or raw_point.get("id")
    point_id = str(raw_point_id).strip() if raw_point_id is not None else f"point-{index + 1}"

    raw_station_id = raw_point.get("station_id")
    station_id: UUID | str | None = (
        _to_optional_uuid(raw_station_id) or str(raw_station_id).strip()
        if raw_station_id is not None
        else None
    )

    raw_label = raw_point.get("label")
    label = str(raw_label).strip() if isinstance(raw_label, str) and raw_label.strip() else None

    raw_quality = raw_point.get("quality")
    quality = (
        str(raw_quality).strip()
        if isinstance(raw_quality, str) and raw_quality.strip()
        else None
    )

    return EstimationPoint(
        point_id=point_id,
        station_id=station_id,
        latitude=latitude,
        longitude=longitude,
        value=float(value),
        label=label,
        quality=quality,
    )


def _extract_points(result: dict[str, Any], variable: str) -> list[EstimationPoint]:
    raw_points = result.get("points")
    if isinstance(raw_points, list):
        points: list[EstimationPoint] = []
        for index, item in enumerate(raw_points):
            if isinstance(item, dict):
                parsed = _parse_point_dict(item, index)
                if parsed is not None:
                    points.append(parsed)
        return points

    raw_predictions = result.get("predictions")
    if isinstance(raw_predictions, list):
        return [
            EstimationPoint(point_id=f"point-{index + 1}", value=float(val))
            for index, val in enumerate(raw_predictions)
            if _is_finite_number(val)
        ]

    if _is_finite_number(result.get("prediction_value")):
        return [
            EstimationPoint(
                point_id="point-1",
                value=float(result["prediction_value"]),
            )
        ]

    if variable in result and _is_finite_number(result[variable]):
        return [
            EstimationPoint(
                point_id="point-1",
                value=float(result[variable]),
            )
        ]

    return []


def _extract_warnings(
    result: dict[str, Any],
    scene: dict[str, Any] | None,
    status_value: str,
    points: list[EstimationPoint],
) -> list[str]:
    raw_warnings = result.get("warnings")
    if raw_warnings is None:
        raw_warnings = result.get("advertencias")

    warnings: list[str] = []
    seen: set[str] = set()

    if isinstance(raw_warnings, list):
        for item in raw_warnings:
            if isinstance(item, str):
                cleaned = item.strip()
                if cleaned and cleaned not in seen:
                    warnings.append(cleaned)
                    seen.add(cleaned)

    is_experimental = bool(
        (scene and scene.get("is_experimental"))
        or result.get("is_experimental")
        or status_value == "experimental"
    )
    if is_experimental and not any("experimental" in w.lower() for w in warnings):
        warnings.append("Estimación generada bajo condición experimental.")

    if not points:
        empty_warning = "La estimación no contiene puntos calculados."
        if empty_warning not in seen:
            warnings.append(empty_warning)

    return warnings


def _extract_usage_limits(
    result: dict[str, Any],
    warnings: list[str],
    points: list[EstimationPoint],
) -> list[str]:
    limits: list[str] = []
    synthetic_flags = (
        result.get("is_synthetic"),
        result.get("dataset_is_synthetic"),
        result.get("scene_is_synthetic"),
    )
    if any(flag is True for flag in synthetic_flags):
        limits.append(
            "El resultado utiliza datos sintéticos y no representa mediciones observacionales reales."
        )

    extrapolation_reported = any(
        point.quality
        and point.quality.strip().upper() in {"EXTRAPOLATED", "EXTRAPOLATION"}
        for point in points
    ) or any(
        "extrapol" in warning.lower()
        or "fuera del rango" in warning.lower()
        or "excede el rango" in warning.lower()
        for warning in warnings
    )
    if extrapolation_reported:
        limits.append(
            "Una o más estimaciones están fuera del rango observado por el modelo (extrapolación)."
        )

    uncertainty = result.get("uncertainty")
    uncertainty_calibrated = result.get("uncertainty_calibrated") is True or (
        isinstance(uncertainty, dict) and uncertainty.get("calibrated") is True
    )
    if not uncertainty_calibrated:
        limits.append(
            "No se dispone de incertidumbre calibrada; el resultado no debe interpretarse como un intervalo de confianza."
        )

    return limits


def build_prediction_detail(
    prediction_row: dict[str, Any],
    scene_row: dict[str, Any] | None = None,
    training_job_row: dict[str, Any] | None = None,
) -> PredictionDetailResponse:
    """Construye la vista detallada de una estimación con trazabilidad y advertencias."""
    result = prediction_row.get("result")
    if not isinstance(result, dict):
        result = {}

    variable = _resolve_variable(result)
    unit = _resolve_unit(result, variable)
    status_value = _resolve_status(result)
    points = _extract_points(result, variable)
    warnings = _extract_warnings(result, scene_row, status_value, points)
    usage_limits = _extract_usage_limits(result, warnings, points)

    raw_rules = prediction_row.get("rules") or []
    rules = [
        AppliedRule.model_validate(rule)
        for rule in raw_rules
        if isinstance(rule, dict)
    ]

    lake_id = _to_optional_uuid(
        scene_row.get("lake_id") if scene_row else result.get("lake_id")
    )
    raw_scene_identifier = (
        scene_row.get("scene_identifier")
        if scene_row
        else result.get("scene_identifier")
    )
    scene_identifier = (
        str(raw_scene_identifier).strip()
        if raw_scene_identifier is not None and str(raw_scene_identifier).strip()
        else None
    )
    raw_acquisition_date = (
        scene_row.get("acquisition_date")
        if scene_row
        else result.get("acquisition_date")
    )
    acquisition_date = (
        str(raw_acquisition_date) if raw_acquisition_date is not None else None
    )

    job_config = (
        training_job_row.get("config")
        if isinstance(training_job_row, dict)
        and isinstance(training_job_row.get("config"), dict)
        else {}
    )
    job_result = (
        training_job_row.get("result")
        if isinstance(training_job_row, dict)
        and isinstance(training_job_row.get("result"), dict)
        else {}
    )

    training_job_id = _to_optional_uuid(
        result.get("training_job_id")
        or (training_job_row.get("id") if training_job_row else None)
    )
    dataset_id = _to_optional_uuid(
        result.get("dataset_id")
        or job_config.get("dataset_id")
        or job_result.get("dataset_id")
    )
    dataset_version_id = _to_optional_uuid(
        result.get("dataset_version_id")
        or (
            training_job_row.get("dataset_version_id")
            if training_job_row
            else None
        )
        or job_config.get("version_id")
        or job_result.get("dataset_version_id")
    )
    raw_model_name = result.get("model_name") or job_result.get("model")
    model_name = (
        str(raw_model_name).strip()
        if isinstance(raw_model_name, str) and raw_model_name.strip()
        else None
    )

    provenance = EstimationProvenance(
        model_version_id=prediction_row["model_version_id"],
        model_name=model_name,
        training_job_id=training_job_id,
        scene_id=prediction_row["scene_id"],
        lake_id=lake_id,
        scene_identifier=scene_identifier,
        acquisition_date=acquisition_date,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        rules=rules,
        generated_at=prediction_row["created_at"],
    )

    return PredictionDetailResponse(
        id=prediction_row["id"],
        organization_id=prediction_row["organization_id"],
        variable=variable,
        unit=unit,
        status=status_value,
        points=points,
        provenance=provenance,
        warnings=warnings,
        usage_limits=usage_limits,
        created_at=prediction_row["created_at"],
    )
