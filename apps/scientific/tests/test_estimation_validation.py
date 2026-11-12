from uuid import uuid4

import pytest

from apps.scientific.app.domains.execution.domain_execution import (
    EstimationInputValidationError,
    validate_estimation_inputs,
)
from apps.scientific.app.domains.execution.schemas_execution import (
    EstimationRequestInput,
    ModelScopeSpec,
    SpectralObservationInput,
)


def _make_base_fixtures():
    lake_id = uuid4()
    scene_id = uuid4()
    model_spec = ModelScopeSpec(
        model_version_id=uuid4(),
        lake_id=lake_id,
        target_variable="chlorophyll_a",
        unit="ug/L",
        required_index="NDCI",
        min_index_value=-0.2,
        max_index_value=0.5,
        status="ACTIVE",
    )
    obs = SpectralObservationInput(
        observation_id=uuid4(),
        lake_id=lake_id,
        scene_id=scene_id,
        spectral_index="NDCI",
        index_value=0.15,
        quality="VALID",
    )
    return lake_id, scene_id, model_spec, obs


def test_validate_estimation_inputs_accepts_compatible_request():
    lake_id, scene_id, model_spec, obs = _make_base_fixtures()
    request = EstimationRequestInput(
        lake_id=lake_id,
        scene_id=scene_id,
        target_variable="clorofila_a",
        unit="µg/L",
        required_index="ndci",
        observations=[obs],
    )

    result = validate_estimation_inputs(model_spec, request)

    assert result.target_variable == "chlorophyll_a"
    assert result.unit == "ug/L"
    assert result.required_index == "NDCI"
    assert result.valid_observation_count == 1
    assert result.warnings == []


def test_validate_estimation_rejects_incompatible_variable():
    lake_id, scene_id, model_spec, obs = _make_base_fixtures()
    request = EstimationRequestInput(
        lake_id=lake_id,
        scene_id=scene_id,
        target_variable="turbidez",
        unit="ug/L",
        required_index="NDCI",
        observations=[obs],
    )

    with pytest.raises(EstimationInputValidationError, match="Variable objetivo incompatible"):
        validate_estimation_inputs(model_spec, request)


def test_validate_estimation_rejects_incompatible_unit():
    lake_id, scene_id, model_spec, obs = _make_base_fixtures()
    request = EstimationRequestInput(
        lake_id=lake_id,
        scene_id=scene_id,
        target_variable="chlorophyll_a",
        unit="ppm",
        required_index="NDCI",
        observations=[obs],
    )

    with pytest.raises(EstimationInputValidationError, match="Unidad incompatible"):
        validate_estimation_inputs(model_spec, request)


def test_validate_estimation_rejects_incompatible_index_in_observation():
    lake_id, scene_id, model_spec, obs = _make_base_fixtures()
    obs_wrong_index = obs.model_copy(update={"spectral_index": "NDVI"})
    request = EstimationRequestInput(
        lake_id=lake_id,
        scene_id=scene_id,
        observations=[obs_wrong_index],
    )

    with pytest.raises(EstimationInputValidationError, match="Índice espectral incompatible"):
        validate_estimation_inputs(model_spec, request)


def test_validate_estimation_rejects_different_lake_or_invalid_quality():
    lake_id, scene_id, model_spec, obs = _make_base_fixtures()
    request_wrong_lake = EstimationRequestInput(
        lake_id=uuid4(),
        scene_id=scene_id,
        observations=[obs],
    )

    with pytest.raises(EstimationInputValidationError, match="Incompatibilidad geográfica"):
        validate_estimation_inputs(model_spec, request_wrong_lake)

    cloudy_obs = obs.model_copy(update={"quality": "CLOUDY"})
    request_cloudy = EstimationRequestInput(
        lake_id=lake_id,
        scene_id=scene_id,
        observations=[cloudy_obs],
    )

    with pytest.raises(EstimationInputValidationError, match="bandera de calidad inválida"):
        validate_estimation_inputs(model_spec, request_cloudy)


def test_validate_estimation_flags_extrapolation_warning():
    lake_id, scene_id, model_spec, obs = _make_base_fixtures()
    model_experimental = model_spec.model_copy(update={"status": "EXPERIMENTAL"})
    extrapolated_obs = obs.model_copy(update={"index_value": 0.85})
    request = EstimationRequestInput(
        lake_id=lake_id,
        scene_id=scene_id,
        observations=[extrapolated_obs],
    )

    result = validate_estimation_inputs(model_experimental, request)

    assert result.valid_observation_count == 1
    assert any("EXPERIMENTAL" in w for w in result.warnings)
    assert any("extrapolación" in w for w in result.warnings)

