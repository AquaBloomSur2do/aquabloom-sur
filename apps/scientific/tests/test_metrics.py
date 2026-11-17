import pytest

from apps.scientific.app.domains.execution.domain_execution import (
    calculate_pilot_metrics,
)


def test_calculate_pilot_metrics_standard_case():
    y_true = [3.0, -0.5, 2.0, 7.0]
    y_pred = [2.5, 0.0, 2.0, 8.0]
    
    result = calculate_pilot_metrics(y_true, y_pred)
    
    assert result.sample_count == 4
    assert result.mae == 0.5000
    assert result.rmse == 0.6124
    assert result.bias == 0.2500
    assert result.r2_computable is True
    assert result.r2 == 0.9486
    assert any("Tamaño de muestra pequeño" in limit for limit in result.limitations)


def test_calculate_pilot_metrics_constant_targets_omits_r2():
    y_true = [5.0, 5.0, 5.0]
    y_pred = [4.0, 5.0, 6.0]
    
    result = calculate_pilot_metrics(y_true, y_pred)
    
    assert result.r2_computable is False
    assert result.r2 is None
    assert any("varianza de observaciones reales es cero" in limit for limit in result.limitations)


def test_calculate_pilot_metrics_single_sample_omits_r2():
    y_true = [10.0]
    y_pred = [9.0]
    
    result = calculate_pilot_metrics(y_true, y_pred)
    
    assert result.sample_count == 1
    assert result.r2_computable is False
    assert result.r2 is None
    assert any("al menos 2 observaciones" in limit for limit in result.limitations)


def test_calculate_pilot_metrics_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="no pueden estar vacías"):
        calculate_pilot_metrics([], [])
        
    with pytest.raises(ValueError, match="misma longitud"):
        calculate_pilot_metrics([1.0, 2.0], [1.0])
