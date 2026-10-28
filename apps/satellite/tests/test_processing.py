import logging

import numpy as np
from app.processing import apply_quality_mask


def test_apply_quality_mask_excludes_pixels_and_records_reasons(caplog):
    raster = np.array([[10, 20, -9999], [40, 50, 60]])
    valid_mask = np.array([[True, False, True], [False, True, True]])
    exclusion_masks = {
        "cloud": np.array([[False, True, False], [False, False, False]]),
        "shadow": np.array([[False, False, False], [True, False, False]]),
    }

    with caplog.at_level(logging.INFO, logger="app.processing"):
        masked_raster, metadata = apply_quality_mask(
            raster,
            valid_mask,
            exclusion_masks=exclusion_masks,
            nodata_value=-9999,
        )

    np.testing.assert_array_equal(
        np.ma.getmaskarray(masked_raster),
        np.array([[False, True, True], [True, False, False]]),
    )
    assert metadata == {
        "excluded_pixel_count": 3,
        "exclusion_reasons": {
            "cloud": 1,
            "shadow": 1,
            "nodata": 1,
            "quality_mask": 0,
        },
    }
    assert "Se excluyeron 3 píxeles por calidad" in caplog.text
    assert "'cloud': 1" in caplog.text
    assert "'shadow': 1" in caplog.text
    assert "'nodata': 1" in caplog.text


def test_apply_quality_mask_masks_all_bands_for_invalid_pixel():
    raster = np.array([[[1, 2], [3, 4]], [[5, 6], [7, 8]]])
    valid_mask = np.array([[True, False], [True, True]])

    masked_raster, metadata = apply_quality_mask(raster, valid_mask)

    np.testing.assert_array_equal(
        np.ma.getmaskarray(masked_raster),
        np.array([[[False, True], [False, False]], [[False, True], [False, False]]]),
    )
    assert metadata == {
        "excluded_pixel_count": 1,
        "exclusion_reasons": {"nodata": 0, "quality_mask": 1},
    }


def test_apply_quality_mask_excludes_nan_nodata_automatically():
    raster = np.array([[1.0, np.nan]])
    valid_mask = np.array([[True, True]])

    masked_raster, metadata = apply_quality_mask(raster, valid_mask)

    np.testing.assert_array_equal(
        np.ma.getmaskarray(masked_raster),
        np.array([[False, True]]),
    )
    assert metadata == {
        "excluded_pixel_count": 1,
        "exclusion_reasons": {"nodata": 1, "quality_mask": 0},
    }
