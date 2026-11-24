from dataclasses import FrozenInstanceError

import pytest

from apps.scientific.app.domains.execution.domain_execution import (
    calculate_pilot_metrics,
)
from apps.scientific.app.domains.execution.evaluation import (
    split_by_acquisition_date,
)
from apps.scientific.app.domains.execution.regression import (
    INITIAL_REGRESSION_CONFIG,
    train_initial_regression,
    train_initial_regression_from_records,
)


def test_train_initial_regression_fits_exact_linear_relationship():
    ndci = [-0.2, 0.0, 0.2, 0.4]
    chlorophyll = [2.0, 5.0, 8.0, 11.0]

    model = train_initial_regression(ndci, chlorophyll)

    assert model.config == INITIAL_REGRESSION_CONFIG
    assert model.config.model_family == "linear_regression"
    assert model.config.solver == "ordinary_least_squares"
    assert model.config.fit_intercept is True
    assert model.config.hyperparameter_search is False
    assert model.is_validated is False
    assert model.sample_count == 4
    assert model.slope == pytest.approx(15.0)
    assert model.intercept == pytest.approx(5.0)
    assert model.feature_min == -0.2
    assert model.feature_max == 0.4
    assert model.target_min == 2.0
    assert model.target_max == 11.0
    assert model.predict_one(0.1) == pytest.approx(6.5)
    assert model.predict([0.1, 0.3]) == pytest.approx((6.5, 9.5))


def test_train_initial_regression_is_deterministic_with_noisy_data():
    ndci = [0.0, 0.1, 0.2, 0.3]
    chlorophyll = [1.0, 2.0, 2.0, 4.0]

    first_model = train_initial_regression(ndci, chlorophyll)
    second_model = train_initial_regression(ndci, chlorophyll)

    assert first_model == second_model
    assert first_model.slope == pytest.approx(9.0)
    assert first_model.intercept == pytest.approx(0.9)

    metadata = first_model.to_metadata()
    assert metadata["hyperparameter_search"] is False
    assert metadata["is_validated"] is False
    assert metadata["observed_feature_range"] == {"minimum": 0.0, "maximum": 0.3}
    assert metadata["observed_target_range"] == {"minimum": 1.0, "maximum": 4.0}


def test_initial_regression_model_and_config_are_immutable():
    model = train_initial_regression([0.0, 0.5], [1.0, 6.0])

    with pytest.raises(FrozenInstanceError):
        model.slope = 0.0  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        model.config.hyperparameter_search = True  # type: ignore[misc]


@pytest.mark.parametrize(
    ("ndci", "chlorophyll", "message"),
    [
        ([], [], "al menos 2 observaciones"),
        ([0.1], [3.0], "al menos 2 observaciones"),
        ([0.1, 0.2], [3.0], "misma longitud"),
        ([0.2, 0.2, 0.2], [1.0, 2.0, 3.0], "varianza nula"),
        ([float("nan"), 0.2], [1.0, 2.0], "debe ser finito"),
        ([0.1, float("inf")], [1.0, 2.0], "debe ser finito"),
        ([0.1, 0.2], [1.0, float("nan")], "debe ser finito"),
        ([-1.1, 0.2], [1.0, 2.0], "dominio físico"),
        ([0.1, 1.5], [1.0, 2.0], "dominio físico"),
        ([0.1, 0.2], [-0.5, 2.0], "no puede ser negativa"),
    ],
)
def test_train_initial_regression_rejects_invalid_values(
    ndci, chlorophyll, message
):
    with pytest.raises(ValueError, match=message):
        train_initial_regression(ndci, chlorophyll)


@pytest.mark.parametrize(
    ("ndci", "chlorophyll"),
    [
        ([True, 0.2], [1.0, 2.0]),
        ([0.1, "0.2"], [1.0, 2.0]),
        ([0.1, 0.2], [1.0, False]),
        ("0.1", [1.0, 2.0]),
    ],
)
def test_train_initial_regression_rejects_invalid_types(ndci, chlorophyll):
    with pytest.raises(TypeError):
        train_initial_regression(ndci, chlorophyll)


def test_predict_validates_inputs():
    model = train_initial_regression([0.0, 0.5], [1.0, 6.0])

    with pytest.raises(ValueError, match="al menos una observación"):
        model.predict([])

    with pytest.raises(ValueError, match="dominio físico"):
        model.predict([1.2])

    with pytest.raises(ValueError, match="debe ser finito"):
        model.predict_one(float("nan"))

    with pytest.raises(TypeError):
        model.predict_one(True)  # type: ignore[arg-type]


def test_train_from_records_integrates_with_temporal_partition_and_metrics():
    records = [
        {"acquisition_date": "2026-01-01", "ndci": -0.2, "chlorophyll_a": 2.0},
        {"acquisition_date": "2026-01-02", "ndci": 0.0, "chlorophyll_a": 4.0},
        {"acquisition_date": "2026-01-03", "ndci": 0.2, "chlorophyll_a": 6.0},
        {"acquisition_date": "2026-01-04", "ndci": 0.4, "chlorophyll_a": 8.0},
        {"acquisition_date": "2026-01-05", "ndci": 0.6, "chlorophyll_a": 10.0},
    ]

    partition = split_by_acquisition_date(records, evaluation_fraction=0.4)
    model = train_initial_regression_from_records(partition.training)

    eval_x = [float(row["ndci"]) for row in partition.evaluation]
    eval_y = [float(row["chlorophyll_a"]) for row in partition.evaluation]
    predictions = list(model.predict(eval_x))
    metrics = calculate_pilot_metrics(eval_y, predictions)

    assert model.sample_count == 3
    assert metrics.mae == 0.0
    assert metrics.rmse == 0.0
    assert metrics.r2_computable is True
    assert metrics.r2 == 1.0


def test_train_from_records_rejects_missing_required_keys():
    with pytest.raises(ValueError, match="no contiene la clave 'ndci'"):
        train_initial_regression_from_records(
            [
                {"chlorophyll_a": 2.0},
                {"ndci": 0.1, "chlorophyll_a": 3.0},
            ]
        )

    with pytest.raises(ValueError, match="no contiene la clave 'chlorophyll_a'"):
        train_initial_regression_from_records(
            [
                {"ndci": 0.0},
                {"ndci": 0.1, "chlorophyll_a": 3.0},
            ]
        )


