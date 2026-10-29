from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from satellite.application.ndci import calculate_ndci, process_pilot_ndci
from satellite.application.schemas import NdciObservationSchema


@pytest.fixture
def multiband_pilot_tif(tmp_path: Path):
    """Crea un archivo GeoTIFF multi-banda sintético (simulando pilot_sentinel2_l2a.tif)

    con bandas B04, B05 y water_mask.
    """
    tif_path = tmp_path / "pilot_sentinel2_l2a.tif"

    b04_data = np.array([[0.1, 0.2], [0.1, 0.1]], dtype=np.float32)
    b05_data = np.array([[0.3, 0.4], [0.5, 0.2]], dtype=np.float32)
    # El píxel (1, 1) está fuera del agua (0 / False)
    water_mask_data = np.array([[1, 1], [1, 0]], dtype=np.uint8)

    transform = from_origin(0, 0, 10, 10)

    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=3,
        dtype=np.float32,
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(b04_data, 1)
        dst.write(b05_data, 2)
        dst.write(water_mask_data, 3)
        dst.set_band_description(1, "B04")
        dst.set_band_description(2, "B05")
        dst.set_band_description(3, "water_mask")

    return tif_path


def test_ndci_scalar_valid():
    result = calculate_ndci(0.3, 0.1)
    assert np.isclose(result, 0.5)


def test_ndci_array_valid():
    b05 = np.array([0.3, 0.5])
    b04 = np.array([0.1, 0.1])
    expected = np.array([0.5, 2.0 / 3.0])
    result = calculate_ndci(b05, b04)
    assert np.allclose(result, expected)


def test_ndci_zero_denominator():
    result = calculate_ndci(0.0, 0.0)
    assert np.isnan(result)

    b05 = np.array([0.0, 0.4])
    b04 = np.array([0.0, 0.2])
    res_array = calculate_ndci(b05, b04)
    assert np.isnan(res_array[0])
    assert np.isclose(res_array[1], 1.0 / 3.0)


def test_ndci_water_mask():
    b05 = np.array([0.3, 0.3])
    b04 = np.array([0.1, 0.1])
    water_mask = np.array([True, False])

    result = calculate_ndci(b05, b04, water_mask=water_mask)
    assert np.isclose(result[0], 0.5)
    assert np.isnan(result[1])


def test_process_pilot_ndci_integration_multiband(multiband_pilot_tif):
    ndci_matrix, schema = process_pilot_ndci(
        raster_path=multiband_pilot_tif,
        lake_id="lago-piloto",
    )

    assert isinstance(ndci_matrix, np.ndarray)
    assert ndci_matrix.shape == (2, 2)

    # El píxel (1, 1) estaba fuera de la máscara de agua, debe ser NaN
    assert not np.isnan(ndci_matrix[0, 0])
    assert not np.isnan(ndci_matrix[0, 1])
    assert not np.isnan(ndci_matrix[1, 0])
    assert np.isnan(ndci_matrix[1, 1])

    assert isinstance(schema, NdciObservationSchema)
    assert schema.lake_id == "lago-piloto"
    assert schema.ndci_value is not None
    assert -1.0 <= schema.ndci_value <= 1.0
    


