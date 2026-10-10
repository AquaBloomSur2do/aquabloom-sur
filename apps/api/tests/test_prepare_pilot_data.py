import hashlib
import json

import numpy as np
import rasterio

from satellite.scripts.prepare_pilot_data import generate_pilot_data


def test_generates_aligned_pilot_raster_and_metadata(tmp_path):
    raster_path, metadata_path = generate_pilot_data(tmp_path)

    assert raster_path.is_file()
    assert metadata_path.is_file()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["acquisition_date"] == "2025-01-15"
    assert metadata["provenance"] == "Synthetic Sentinel-2 L2A Pilot"
    assert metadata["is_synthetic"] is True
    assert metadata["sha256"] == hashlib.sha256(raster_path.read_bytes()).hexdigest()

    with rasterio.open(raster_path) as dataset:
        assert (dataset.width, dataset.height, dataset.count) == (100, 100, 3)
        assert dataset.descriptions == ("B04", "B05", "water_mask")
        assert dataset.crs.to_string() == metadata["crs"]
        assert dataset.transform.to_gdal() == tuple(metadata["transform"])
        assert dataset.read(1).shape == dataset.read(2).shape == dataset.read(3).shape
        assert set(np.unique(dataset.read(3))) == {0, 1}
