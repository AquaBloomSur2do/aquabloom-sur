import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from scripts.prepare_pilot_data import generate_pilot_data


def test_static_binary_hash_matches_metadata():
    data_dir = Path(__file__).resolve().parents[1] / "data"
    metadata = json.loads((data_dir / "metadata.json").read_text(encoding="utf-8"))

    with (data_dir / "pilot_sentinel2_l2a.tif").open("rb") as binary_file:
        binary_hash = hashlib.sha256(binary_file.read()).hexdigest()

    assert binary_hash == metadata["sha256"]


def test_generates_aligned_pilot_raster_and_metadata(tmp_path):
    raster_path, metadata_path = generate_pilot_data(tmp_path)

    assert raster_path.is_file()
    assert metadata_path.is_file()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["acquisition_date"] == "2025-01-15"
    assert metadata["provenance"] == "Synthetic Sentinel-2 L2A Pilot"
    assert metadata["is_synthetic"] is True
    fixture = metadata["pilot_fixture"]
    assert fixture["dataset_version"] == "pilot-fixture-v1"
    assert fixture["dataset_is_synthetic"] is True
    assert fixture["scene_identifier"] == "SYNTHETIC_SENTINEL2_L2A_PILOT_20250115"
    assert fixture["scene_is_synthetic"] is True
    assert fixture["random_seed"] == 20250115
    assert {item["name"] for item in fixture["inputs"]} == {
        "B04",
        "B05",
        "water_mask",
    }
    assert all(item["is_synthetic"] is True for item in fixture["inputs"])
    assert metadata["sha256"] == hashlib.sha256(raster_path.read_bytes()).hexdigest()

    with rasterio.open(raster_path) as dataset:
        assert (dataset.width, dataset.height, dataset.count) == (100, 100, 3)
        assert dataset.descriptions == ("B04", "B05", "water_mask")
        assert dataset.crs.to_string() == metadata["crs"]
        assert dataset.transform.to_gdal() == tuple(metadata["transform"])
        assert dataset.read(1).shape == dataset.read(2).shape == dataset.read(3).shape
        assert set(np.unique(dataset.read(3))) == {0, 1}


def test_seed_reproduces_raster_and_changes_its_values(tmp_path):
    first_path, _ = generate_pilot_data(tmp_path / "first", seed=17)
    repeat_path, _ = generate_pilot_data(tmp_path / "repeat", seed=17)
    changed_path, changed_metadata_path = generate_pilot_data(
        tmp_path / "changed", seed=18
    )

    assert first_path.read_bytes() == repeat_path.read_bytes()
    assert first_path.read_bytes() != changed_path.read_bytes()
    changed_metadata = json.loads(changed_metadata_path.read_text(encoding="utf-8"))
    assert changed_metadata["pilot_fixture"]["random_seed"] == 18


def test_seed_must_be_a_non_negative_integer(tmp_path):
    for seed in (-1, 1.5, True):
        with pytest.raises(
            ValueError, match="La semilla debe ser un entero no negativo."
        ):
            generate_pilot_data(tmp_path, seed=seed)
