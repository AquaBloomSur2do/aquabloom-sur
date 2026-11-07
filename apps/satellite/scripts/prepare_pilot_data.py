import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

PILOT_WIDTH = 100
PILOT_HEIGHT = 100
PROVENANCE = "Synthetic Sentinel-2 L2A Pilot"
DEFAULT_ACQUISITION_DATE = "2025-01-15"


def generate_pilot_data(
    output_dir: Path, acquisition_date: str = DEFAULT_ACQUISITION_DATE
) -> tuple[Path, Path]:
    date.fromisoformat(acquisition_date)
    output_dir.mkdir(parents=True, exist_ok=True)
    raster_path = output_dir / "pilot_sentinel2_l2a.tif"
    metadata_path = output_dir / "metadata.json"

    rows, columns = np.indices((PILOT_HEIGHT, PILOT_WIDTH))
    band_b04 = (900 + columns * 3 + rows * 2).astype(np.uint16)
    band_b05 = (1300 + columns * 4 + rows * 2).astype(np.uint16)
    water_mask = (
        (columns - PILOT_WIDTH // 2) ** 2 + (rows - PILOT_HEIGHT // 2) ** 2 <= 38**2
    ).astype(np.uint16)
    transform = from_origin(700_000, 5_700_000, 10, 10)

    with rasterio.open(
        raster_path,
        "w",
        driver="GTiff",
        width=PILOT_WIDTH,
        height=PILOT_HEIGHT,
        count=3,
        dtype="uint16",
        crs="EPSG:32718",
        transform=transform,
        compress="deflate",
    ) as dataset:
        dataset.write(band_b04, 1)
        dataset.write(band_b05, 2)
        dataset.write(water_mask, 3)
        dataset.set_band_description(1, "B04")
        dataset.set_band_description(2, "B05")
        dataset.set_band_description(3, "water_mask")

    checksum = hashlib.sha256(raster_path.read_bytes()).hexdigest()
    metadata = {
        "acquisition_date": acquisition_date,
        "provenance": PROVENANCE,
        "is_synthetic": True,
        "raster_file": raster_path.name,
        "sha256": checksum,
        "width": PILOT_WIDTH,
        "height": PILOT_HEIGHT,
        "crs": "EPSG:32718",
        "transform": list(transform.to_gdal()),
        "bands": {"B04": 1, "B05": 2, "water_mask": 3},
        "reflectance_scale": 10000,
        "water_mask_values": {"invalid": 0, "water": 1},
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return raster_path, metadata_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic Sentinel-2 pilot data."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data",
    )
    parser.add_argument("--date", default=DEFAULT_ACQUISITION_DATE)
    args = parser.parse_args()

    raster_path, metadata_path = generate_pilot_data(args.output_dir, args.date)
    print(f"Created {raster_path} and {metadata_path}")


if __name__ == "__main__":
    main()
