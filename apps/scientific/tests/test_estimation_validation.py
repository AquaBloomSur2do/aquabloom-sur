from uuid import uuid4

import pytest

from app.estimation_validation import (
    EstimationInputValidationError,
    EstimationRequestInput,
    ModelScopeSpec,
    SpectralObservationInput,
    validate_estimation_inputs,
)


def _build_valid_fixtures():
    model_id = uuid4()
    lake_id = uuid4()
    scene_id = uuid4()

    model = ModelScopeSpec(
        model_version_id=model_id,
        lake_id=lake_id,
        target_variable="chlorophyll_a",
        unit="ug/L",
        required_index="NDCI",
        status="EXPERIMENTAL",
        min_index_value=-0.2,
        max_index_value=0.4,
    )

    obs = SpectralObservationInput(
        observation_id=uuid4(),
        scene_id=scene_id,
        lake_id=lake_id,
        station_id=uuid4(),
        index_name="NDCI",
        index_value=0.15,
        quality_flag="VALID",
    )

    req = EstimationRequestInput(
        model_version_id=model_id,
        scene_id=scene_id,
        lake_id=lake_id,
        target_variable="clorofila_a",
        unit="µg/L",
        required_index="ndci",
        observations=[obs],
    )
    return model, req


def test_validate_estimation_inputs_accepts_compatible_request():
    model, req = _build_valid_fixtures()

    result = validate_estimation_inputs(model, req)

    assert result.model_version_id == model.model_version_id
    assert result.target_variable == "chlorophyll_a"
    assert result.unit == "ug/L"
    assert result.index_name == "NDCI"
    assert len(result.valid_observations) == 1
    assert any("experimental" in w.lower() for w in result.warnings)


def test_validate_estimation_rejects_incompatible_variable():
    model, req = _build_valid_fixtures()
    req.target_variable = "turbidez"

    with pytest.raises(EstimationInputValidationError, match="Variable objetivo"):
        validate_estimation_inputs(model, req)


def test_validate_estimation_rejects_incompatible_unit():
    model, req = _build_valid_fixtures()
    req.unit = "ppm"

    with pytest.raises(EstimationInputValidationError, match="Unidad"):
        validate_estimation_inputs(model, req)


def test_validate_estimation_rejects_incompatible_index_in_observation():
    model, req = _build_valid_fixtures()
    req.observations[0].index_name = "NDVI"

    with pytest.raises(EstimationInputValidationError, match="incompatible con el índice requerido"):
        validate_estimation_inputs(model, req)


def test_validate_estimation_rejects_different_lake_or_invalid_quality():
    model, req = _build_valid_fixtures()
    req.lake_id = uuid4()

    with pytest.raises(EstimationInputValidationError, match="Incompatibilidad geográfica"):
        validate_estimation_inputs(model, req)

    model2, req2 = _build_valid_fixtures()
    req2.observations[0].quality_flag = "CLOUDY"

    with pytest.raises(EstimationInputValidationError, match="calidad insuficiente"):
        validate_estimation_inputs(model2, req2)


def test_validate_estimation_flags_extrapolation_warning():
    model, req = _build_valid_fixtures()
    req.observations[0].index_value = 0.75  # Dentro de [-1, 1], pero sobre max_index_value (0.4)

    result = validate_estimation_inputs(model, req)

    assert len(result.valid_observations) == 1
    assert any("extrapolación" in w.lower() for w in result.warnings)
