import numpy as np

from app.indices import calculate_ndwi


def test_calculate_ndwi_uses_mcfeeters_formula():
    green = np.array([3.0, 5.0])
    nir = np.array([1.0, 3.0])

    result = calculate_ndwi(green, nir)

    np.testing.assert_allclose(result, np.array([0.5, 0.25]))


def test_calculate_ndwi_preserves_nan_values():
    green = np.array([3.0, np.nan])
    nir = np.array([1.0, 2.0])

    result = calculate_ndwi(green, nir)

    assert result[0] == 0.5
    assert np.isnan(result[1])


def test_calculate_ndwi_preserves_masks_and_masks_zero_denominators():
    green = np.ma.array([3.0, 4.0, 0.0], mask=[False, True, False])
    nir = np.array([1.0, 2.0, 0.0])

    result = calculate_ndwi(green, nir)

    np.testing.assert_array_equal(np.ma.getmaskarray(result), [False, True, True])
    assert result[0] == 0.5


def test_calculate_ndwi_returns_nan_for_zero_denominators():
    green = np.array([0.0, 3.0])
    nir = np.array([0.0, -3.0])

    result = calculate_ndwi(green, nir)

    assert np.isnan(result).all()
