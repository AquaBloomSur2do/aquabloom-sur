import math
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_PILOT_VARIABLES = {"chlorophyll_a", "clorofila_a"}
ALLOWED_PILOT_UNITS = {"ug/l", "µg/l", "mg/m3"}
ALLOWED_PILOT_INDICES = {"NDCI"}


class EstimationInputValidationError(ValueError):
    """Excepción lanzada cuando el modelo o las observaciones son incompatibles para estimación."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _normalize_variable(value: str) -> str:
    norm = value.strip().lower()
    if norm in {"clorofila_a", "chlorophyll_a", "chl_a", "chla"}:
        return "chlorophyll_a"
    return norm


def _normalize_unit(value: str) -> str:
    norm = value.strip().lower().replace("μ", "u").replace("µ", "u")
    if norm in {"ug/l", "mg/m3"}:
        return "ug/L"
    return value.strip()


def _normalize_index(value: str) -> str:
    return value.strip().upper()


class ModelScopeSpec(BaseModel):
    """Alcance y metadatos del modelo contra los cuales se valida la solicitud de estimación."""

    model_version_id: UUID
    lake_id: UUID
    target_variable: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    required_index: str = Field(default="NDCI", min_length=1)
    status: Literal["EXPERIMENTAL", "VALIDATED", "DEPRECATED", "REJECTED"] = "EXPERIMENTAL"
    min_index_value: float = -1.0
    max_index_value: float = 1.0

    model_config = ConfigDict(from_attributes=True)


class SpectralObservationInput(BaseModel):
    """Observación espectral puntual proveniente de una escena para inferencia."""

    observation_id: UUID
    scene_id: UUID
    lake_id: UUID
    station_id: UUID | None = None
    index_name: str = Field(min_length=1)
    index_value: float
    unit: str = Field(default="dimensionless", min_length=1)
    quality_flag: Literal["VALID", "CLOUDY", "INVALID", "MASKED"] = "VALID"

    model_config = ConfigDict(from_attributes=True)

    @field_validator("index_value")
    @classmethod
    def validate_finite_index(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("El valor del índice espectral debe ser un número finito.")
        return value


class EstimationRequestInput(BaseModel):
    """Solicitud de estimación a validar antes de crear o ejecutar el trabajo."""

    model_version_id: UUID
    scene_id: UUID
    lake_id: UUID
    target_variable: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    required_index: str = Field(default="NDCI", min_length=1)
    observations: list[SpectralObservationInput] = Field(min_length=1)

    model_config = ConfigDict(from_attributes=True)


class ValidatedEstimationInput(BaseModel):
    """Resultado validado listo para encolar o ejecutar la inferencia en el worker."""

    model_version_id: UUID
    scene_id: UUID
    lake_id: UUID
    target_variable: str
    unit: str
    index_name: str
    valid_observations: list[SpectralObservationInput]
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


def validate_estimation_inputs(
    model_scope: ModelScopeSpec,
    request_input: EstimationRequestInput,
) -> ValidatedEstimationInput:
    """
    Valida que el modelo seleccionado y las observaciones espectrales sean compatibles (S2-169):
    1. El modelo debe coincidir en ID, estar activo (EXPERIMENTAL o VALIDATED) y pertenecer al mismo lago.
    2. La variable objetivo, su unidad y el índice espectral deben pertenecer al piloto y coincidir con el modelo.
    3. Todas las observaciones deben pertenecer a la misma escena y lago, usar el índice exigido,
       tener bandera de calidad VALID y encontrarse en el rango físico [-1, 1].
    """
    if model_scope.model_version_id != request_input.model_version_id:
        raise EstimationInputValidationError(
            "El identificador model_version_id de la solicitud no coincide con el modelo cargado."
        )

    if model_scope.status in {"DEPRECATED", "REJECTED"}:
        raise EstimationInputValidationError(
            f"El modelo seleccionado no es apto para estimación (estado: {model_scope.status})."
        )

    if model_scope.lake_id != request_input.lake_id:
        raise EstimationInputValidationError(
            "Incompatibilidad geográfica: el modelo fue entrenado para un lago distinto al solicitado."
        )

    req_var_raw = request_input.target_variable.strip().lower()
    if req_var_raw not in ALLOWED_PILOT_VARIABLES:
        raise EstimationInputValidationError(
            f"Variable objetivo '{request_input.target_variable}' no soportada en el piloto. "
            "Solo se admite clorofila_a / chlorophyll_a."
        )

    model_var = _normalize_variable(model_scope.target_variable)
    req_var = _normalize_variable(request_input.target_variable)
    if model_var != req_var:
        raise EstimationInputValidationError(
            f"Variable incompatible: el modelo predice '{model_scope.target_variable}', "
            f"pero se solicitó '{request_input.target_variable}'."
        )

    req_unit_raw = request_input.unit.strip().lower().replace("μ", "u")
    if req_unit_raw not in ALLOWED_PILOT_UNITS:
        raise EstimationInputValidationError(
            f"Unidad '{request_input.unit}' incompatible con el piloto. "
            "Use 'ug/L' o 'mg/m3'."
        )

    model_unit = _normalize_unit(model_scope.unit)
    req_unit = _normalize_unit(request_input.unit)
    if model_unit != req_unit:
        raise EstimationInputValidationError(
            f"Unidad incompatible: el modelo opera en '{model_scope.unit}', "
            f"pero se solicitó '{request_input.unit}'."
        )

    req_index = _normalize_index(request_input.required_index)
    model_index = _normalize_index(model_scope.required_index)
    if req_index not in ALLOWED_PILOT_INDICES:
        raise EstimationInputValidationError(
            f"Índice espectral '{request_input.required_index}' no soportado en el piloto. "
            "Solo se admite 'NDCI'."
        )

    if req_index != model_index:
        raise EstimationInputValidationError(
            f"Índice incompatible: el modelo requiere '{model_index}', "
            f"pero se solicitó '{req_index}'."
        )

    warnings: list[str] = []
    if model_scope.status == "EXPERIMENTAL":
        warnings.append(
            "Estimación experimental (RN-07 / RN-08): el modelo no cuenta con activación oficial validada."
        )

    extrapolated_count = 0

    for obs in request_input.observations:
        if obs.lake_id != request_input.lake_id:
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} pertenece a un lago distinto al de la estimación."
            )

        if obs.scene_id != request_input.scene_id:
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} no pertenece a la escena solicitada ({request_input.scene_id})."
            )

        obs_index = _normalize_index(obs.index_name)
        if obs_index != model_index:
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} entrega el índice '{obs.index_name}', "
                f"incompatible con el índice requerido '{model_index}'."
            )

        if obs.quality_flag != "VALID":
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} fue rechazada por calidad insuficiente "
                f"(quality_flag='{obs.quality_flag}')."
            )

        if not (-1.0 <= obs.index_value <= 1.0):
            raise EstimationInputValidationError(
                f"La observación {obs.observation_id} tiene un valor de {model_index} fuera del "
                f"dominio físico [-1.0, 1.0]: {obs.index_value}."
            )

        if obs.index_value < model_scope.min_index_value or obs.index_value > model_scope.max_index_value:
            extrapolated_count += 1

    if extrapolated_count > 0:
        warnings.append(
            f"Extrapolación detectada en {extrapolated_count} punto(s): valores de {model_index} "
            f"fuera del rango observado en entrenamiento [{model_scope.min_index_value}, {model_scope.max_index_value}]."
        )

    return ValidatedEstimationInput(
        model_version_id=model_scope.model_version_id,
        scene_id=request_input.scene_id,
        lake_id=request_input.lake_id,
        target_variable=model_var,
        unit=model_unit,
        index_name=model_index,
        valid_observations=request_input.observations,
        warnings=warnings,
    )
