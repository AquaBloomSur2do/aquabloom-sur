import math

import pytest

from app.metrics import MetricsValidationError, calculate_pilot_metrics


def test_calculate_pilot_metrics_standard_case():
    y_true = [2.0, 4.0, 6.0, 8.0]
    y_pred = [2.5, 3.5, 6.5, 8.5]
    # errores (pred - true): [+0.5, -0.5, +0.5, +0.5]
    # MAE = 2.0 / 4 = 0.5
    # RMSE = sqrt(1.0 / 4) = 0.5
    # Bias = 1.0 / 4 = +0.25
    # mean_true = 5.0 -> SS_tot = 9 + 1 + 1 + 9 = 20.0
    # SS_res = 1.0 -> R² = 1 - (1 / 20) = 0.95

    result = calculate_pilot_metrics(y_true, y_pred)

    assert result.sample_count == 4
    assert math.isclose(result.mae, 0.5, rel_tol=1e-6)
    assert math.isclose(result.rmse, 0.5, rel_tol=1e-6)
    assert math.isclose(result.bias, 0.25, rel_tol=1e-6)
    assert result.r2_computable is True
    assert result.r2 is not None
    assert math.isclose(result.r2, 0.95, rel_tol=1e-6)
    assert any("RNF-26" in lim for lim in result.limitations)
    assert any("n=4" in lim for lim in result.limitations)


def test_calculate_pilot_metrics_constant_targets_omits_r2():
    y_true = [5.0, 5.0, 5.0]
    y_pred = [4.0, 5.0, 6.0]

    result = calculate_pilot_metrics(y_true, y_pred)

    assert result.sample_count == 3
    assert math.isclose(result.mae, 2.0 / 3.0, rel_tol=1e-5)
    assert math.isclose(result.bias, 0.0, abs_tol=1e-6)
    assert result.r2 is None
    assert result.r2_computable is False
    assert any("varianza" in lim.lower() for lim in result.limitations)


def test_calculate_pilot_metrics_single_sample_omits_r2():
    result = calculate_pilot_metrics([10.0], [8.5])

    assert result.sample_count == 1
    assert result.mae == 1.5
    assert result.rmse == 1.5
    assert result.bias == -1.5
    assert result.r2 is None
    assert result.r2_computable is False
    assert any("n < 2" in lim for lim in result.limitations)


def test_calculate_pilot_metrics_rejects_invalid_inputs():
    with pytest.raises(MetricsValidationError, match="vacías"):
        calculate_pilot_metrics([], [])

    with pytest.raises(MetricsValidationError, match="incompatibles"):
        calculate_pilot_metrics([1.0, 2.0], [1.0])

    with pytest.raises(MetricsValidationError, match="no finito"):
        calculate_pilot_metrics([1.0, float("nan")], [1.0, 2.0])
