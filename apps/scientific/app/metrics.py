import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class MetricsValidationError(ValueError):
    """Error lanzado cuando las entradas para el cálculo de métricas son inválidas."""


class PilotMetricsResult(BaseModel):
    """Contrato de salida para las métricas de evaluación del modelo piloto (S2-157)."""

    sample_count: int = Field(ge=1, description="Número de observaciones evaluadas (n).")
    mae: float = Field(ge=0.0, description="Error Absoluto Medio (MAE).")
    rmse: float = Field(ge=0.0, description="Raíz del Error Cuadrático Medio (RMSE).")
    bias: float = Field(description="Sesgo medio (Media de y_pred - y_true).")
    r2: float | None = Field(
        default=None,
        description="Coeficiente de determinación (R²), calculado solo si existe varianza y n >= 2.",
    )
    r2_computable: bool = Field(
        description="Indica si fue matemáticamente viable calcular R²."
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Advertencias científicas e interpretación conjunta obligatoria (RNF-26).",
    )

    model_config = ConfigDict(from_attributes=True)


def calculate_pilot_metrics(
    y_true: Sequence[float],
    y_pred: Sequence[float],
) -> PilotMetricsResult:
    """
    Calcula las métricas del piloto científico (MAE, RMSE, sesgo y R² condicional):
    - MAE = (1/n) * sum(|y_pred - y_true|)
    - RMSE = sqrt((1/n) * sum((y_pred - y_true)^2))
    - Sesgo (Bias) = (1/n) * sum(y_pred - y_true)
    - R² = 1 - (SS_res / SS_tot), solo cuando n >= 2 y SS_tot > 0.
    """
    if len(y_true) != len(y_pred):
        raise MetricsValidationError(
            f"Longitudes incompatibles: y_true ({len(y_true)}) vs y_pred ({len(y_pred)})."
        )

    n = len(y_true)
    if n == 0:
        raise MetricsValidationError(
            "No se pueden calcular métricas sobre secuencias vacías."
        )

    clean_true: list[float] = []
    clean_pred: list[float] = []

    for idx, (t_val, p_val) in enumerate(zip(y_true, y_pred, strict=True)):
        try:
            t_float = float(t_val)
            p_float = float(p_val)
        except (TypeError, ValueError) as exc:
            raise MetricsValidationError(
                f"Valor no numérico detectado en el índice {idx}."
            ) from exc

        if not (math.isfinite(t_float) and math.isfinite(p_float)):
            raise MetricsValidationError(
                f"Valor no finito (NaN o Inf) detectado en el índice {idx}."
            )

        clean_true.append(t_float)
        clean_pred.append(p_float)

    errors = [p - t for t, p in zip(clean_true, clean_pred, strict=True)]
    abs_errors = [abs(err) for err in errors]
    sq_errors = [err * err for err in errors]

    mae = sum(abs_errors) / n
    rmse = math.sqrt(sum(sq_errors) / n)
    bias = sum(errors) / n

    limitations: list[str] = [
        "R² no debe interpretarse de manera aislada; evalúe conjuntamente MAE, RMSE y sesgo (RNF-26)."
    ]

    mean_true = sum(clean_true) / n
    ss_tot = sum((t - mean_true) ** 2 for t in clean_true)
    ss_res = sum(sq_errors)

    r2: float | None = None
    r2_computable = False

    if n < 2:
        limitations.append(
            "R² no es calculable con menos de 2 observaciones en la partición de evaluación (n < 2)."
        )
    elif math.isclose(ss_tot, 0.0, abs_tol=1e-12):
        limitations.append(
            "R² no es calculable porque las observaciones reales carecen de varianza (valores constantes, SS_tot = 0)."
        )
    else:
        r2 = round(1.0 - (ss_res / ss_tot), 6)
        r2_computable = True
        if n < 10:
            limitations.append(
                f"Tamaño muestral reducido (n={n}): R² presenta alta sensibilidad a valores atípicos en el piloto experimental."
            )

    return PilotMetricsResult(
        sample_count=n,
        mae=round(mae, 6),
        rmse=round(rmse, 6),
        bias=round(bias, 6),
        r2=r2,
        r2_computable=r2_computable,
        limitations=limitations,
    )
