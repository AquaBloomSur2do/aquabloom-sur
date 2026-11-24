"""Modelo inicial de regresión lineal simple con configuración fija (S2-156).

Implementa un único estimador determinista por Mínimos Cuadrados Ordinarios (OLS)
sin búsqueda de hiperparámetros ni selección automática de modelos, mapeando el
índice espectral piloto (NDCI) hacia concentración de clorofila-a (ug/L).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

MIN_TRAINING_SAMPLES = 2
NDCI_MIN_BOUND = -1.0
NDCI_MAX_BOUND = 1.0
VARIANCE_ABS_TOL = 1e-12


@dataclass(frozen=True)
class InitialRegressionConfig:
    """Configuración fija e inmutable del modelo inicial (sin búsqueda de hiperparámetros)."""

    model_family: Literal["linear_regression"] = "linear_regression"
    solver: Literal["ordinary_least_squares"] = "ordinary_least_squares"
    fit_intercept: Literal[True] = True
    hyperparameter_search: Literal[False] = False
    feature_name: Literal["NDCI"] = "NDCI"
    target_variable: Literal["chlorophyll_a"] = "chlorophyll_a"
    unit: Literal["ug/L"] = "ug/L"


INITIAL_REGRESSION_CONFIG = InitialRegressionConfig()


def _validate_numeric(value: object, field_name: str, position: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"El valor de {field_name} en la posición {position} debe ser numérico."
        )
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(
            f"El valor de {field_name} en la posición {position} debe ser finito (sin NaN ni Inf)."
        )
    return numeric


def _validate_ndci(value: object, position: int) -> float:
    ndci = _validate_numeric(value, "NDCI", position)
    if ndci < NDCI_MIN_BOUND or ndci > NDCI_MAX_BOUND:
        raise ValueError(
            f"El valor de NDCI ({ndci}) en la posición {position} está fuera del dominio físico [-1.0, 1.0]."
        )
    return ndci


def _validate_chlorophyll(value: object, position: int) -> float:
    chlorophyll = _validate_numeric(value, "chlorophyll_a", position)
    if chlorophyll < 0.0:
        raise ValueError(
            f"La concentración de chlorophyll_a ({chlorophyll}) en la posición {position} no puede ser negativa."
        )
    return chlorophyll


@dataclass(frozen=True)
class InitialRegressionModel:
    """Artefacto inmutable del modelo lineal inicial ajustado por OLS."""

    config: InitialRegressionConfig
    slope: float
    intercept: float
    sample_count: int
    feature_min: float
    feature_max: float
    target_min: float
    target_max: float
    is_validated: Literal[False] = False

    def predict_one(self, ndci_value: float) -> float:
        """Evalúa la ecuación lineal y = intercept + slope * x para una observación NDCI."""
        x_val = _validate_ndci(ndci_value, 1)
        return self.intercept + (self.slope * x_val)

    def predict(self, ndci_values: Sequence[float]) -> tuple[float, ...]:
        """Genera predicciones deterministas para una secuencia de observaciones NDCI."""
        if isinstance(ndci_values, (str, bytes)) or not isinstance(
            ndci_values, Sequence
        ):
            raise TypeError("ndci_values debe ser una secuencia numérica.")
        if not ndci_values:
            raise ValueError(
                "Se requiere al menos una observación NDCI para predecir."
            )
        return tuple(
            self.intercept + (self.slope * _validate_ndci(value, idx))
            for idx, value in enumerate(ndci_values, start=1)
        )

    def to_metadata(self) -> dict[str, object]:
        """Serializa los parámetros y metadatos fijos del modelo para trazabilidad."""
        return {
            "model_family": self.config.model_family,
            "solver": self.config.solver,
            "fit_intercept": self.config.fit_intercept,
            "hyperparameter_search": self.config.hyperparameter_search,
            "feature_name": self.config.feature_name,
            "target_variable": self.config.target_variable,
            "unit": self.config.unit,
            "slope": self.slope,
            "intercept": self.intercept,
            "sample_count": self.sample_count,
            "observed_feature_range": {
                "minimum": self.feature_min,
                "maximum": self.feature_max,
            },
            "observed_target_range": {
                "minimum": self.target_min,
                "maximum": self.target_max,
            },
            "is_validated": self.is_validated,
        }


def train_initial_regression(
    ndci_values: Sequence[float],
    chlorophyll_values: Sequence[float],
) -> InitialRegressionModel:
    """Ajusta una regresión lineal simple (OLS) con configuración fija (S2-156).

    No ejecuta búsqueda de hiperparámetros ni selección de modelos; utiliza la
    solución analítica cerrada de mínimos cuadrados ordinarios con intercepto.
    """
    if isinstance(ndci_values, (str, bytes)) or not isinstance(
        ndci_values, Sequence
    ):
        raise TypeError("ndci_values debe ser una secuencia numérica.")
    if isinstance(chlorophyll_values, (str, bytes)) or not isinstance(
        chlorophyll_values, Sequence
    ):
        raise TypeError("chlorophyll_values debe ser una secuencia numérica.")

    if len(ndci_values) != len(chlorophyll_values):
        raise ValueError(
            "Las secuencias de NDCI y chlorophyll_a deben tener exactamente la misma longitud."
        )
    if len(ndci_values) < MIN_TRAINING_SAMPLES:
        raise ValueError(
            "Se requieren al menos 2 observaciones para ajustar la regresión inicial."
        )

    validated_x: list[float] = []
    validated_y: list[float] = []
    for position, (raw_x, raw_y) in enumerate(
        zip(ndci_values, chlorophyll_values, strict=True), start=1
    ):
        validated_x.append(_validate_ndci(raw_x, position))
        validated_y.append(_validate_chlorophyll(raw_y, position))

    sample_count = len(validated_x)
    mean_x = sum(validated_x) / sample_count
    mean_y = sum(validated_y) / sample_count

    s_xx = sum((x_val - mean_x) ** 2 for x_val in validated_x)
    if math.isclose(s_xx, 0.0, abs_tol=VARIANCE_ABS_TOL):
        raise ValueError(
            "La variable predictora NDCI tiene varianza nula; no es posible ajustar la regresión lineal."
        )

    s_xy = sum(
        (x_val - mean_x) * (y_val - mean_y)
        for x_val, y_val in zip(validated_x, validated_y, strict=True)
    )
    slope = s_xy / s_xx
    intercept = mean_y - (slope * mean_x)

    return InitialRegressionModel(
        config=INITIAL_REGRESSION_CONFIG,
        slope=slope,
        intercept=intercept,
        sample_count=sample_count,
        feature_min=min(validated_x),
        feature_max=max(validated_x),
        target_min=min(validated_y),
        target_max=max(validated_y),
    )


def train_initial_regression_from_records(
    records: Sequence[Mapping[str, object]],
) -> InitialRegressionModel:
    """Ajusta el modelo inicial directamente desde registros de entrenamiento particionados."""
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise TypeError("records debe ser una secuencia de diccionarios.")
    if len(records) < MIN_TRAINING_SAMPLES:
        raise ValueError(
            "Se requieren al menos 2 registros para ajustar la regresión inicial."
        )

    ndci_values: list[float] = []
    chlorophyll_values: list[float] = []
    for position, record in enumerate(records, start=1):
        if not isinstance(record, Mapping):
            raise TypeError(
                f"El registro {position} debe ser un mapeo con claves 'ndci' y 'chlorophyll_a'."
            )
        if "ndci" not in record:
            raise ValueError(f"El registro {position} no contiene la clave 'ndci'.")
        if "chlorophyll_a" not in record:
            raise ValueError(
                f"El registro {position} no contiene la clave 'chlorophyll_a'."
            )
        ndci_values.append(_validate_ndci(record["ndci"], position))
        chlorophyll_values.append(
            _validate_chlorophyll(record["chlorophyll_a"], position)
        )

    return train_initial_regression(ndci_values, chlorophyll_values)


