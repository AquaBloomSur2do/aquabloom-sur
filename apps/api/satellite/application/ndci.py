from pathlib import Path

import numpy as np
import rasterio

from satellite.application.schemas import NdciObservationSchema

DATA_DIR = Path(__file__).parent.parent / "data"


def calculate_ndci(
    b05: np.ndarray | float,
    b04: np.ndarray | float,
    water_mask: np.ndarray | None = None,
) -> np.ndarray | float:
    """Calcula el Normalized Difference Chlorophyll Index (NDCI).

    Fórmula: NDCI = (B05 - B04) / (B05 + B04)
    """
    b05_arr = np.asarray(b05, dtype=np.float64)
    b04_arr = np.asarray(b04, dtype=np.float64)

    numerator = b05_arr - b04_arr
    denominator = b05_arr + b04_arr

    with np.errstate(divide="ignore", invalid="ignore"):
        ndci = np.where(denominator != 0, numerator / denominator, np.nan)

    if water_mask is not None:
        mask_arr = np.asarray(water_mask, dtype=bool)
        ndci = np.where(mask_arr, ndci, np.nan)

    if np.ndim(b05) == 0 and np.ndim(b04) == 0:
        val = float(ndci.item())
        return val if not np.isnan(val) else np.nan

    return ndci


def process_pilot_ndci(
    raster_path: Path | str | None = None,
    lake_id: str = "lago-piloto",
    b04_band: int | str = "B04",
    b05_band: int | str = "B05",
    water_mask_band: int | str | None = "water_mask",
) -> tuple[np.ndarray, NdciObservationSchema]:
    """Lee el raster preparado multi-banda GeoTIFF del piloto (pilot_sentinel2_l2a.tif),

    extrae las bandas B04, B05 y la máscara de agua, y calcula el índice NDCI.
    """
    if raster_path is None:
        raster_path = DATA_DIR / "pilot_sentinel2_l2a.tif"

    raster_path = Path(raster_path)

    if not raster_path.exists():
        raise FileNotFoundError(
            f"No se encontró el raster preparado en {raster_path}"
        )

    with rasterio.open(raster_path) as src:
        descriptions = [d.upper() if d else "" for d in (src.descriptions or [])]

        b04_idx = _resolve_band_index(src, b04_band, descriptions, default_idx=1)
        b05_idx = _resolve_band_index(src, b05_band, descriptions, default_idx=2)
        mask_idx = (
            _resolve_band_index(src, water_mask_band, descriptions, default_idx=None)
            if water_mask_band is not None
            else None
        )

        b04_data = src.read(b04_idx)
        b05_data = src.read(b05_idx)

        water_mask = None
        if mask_idx is not None and mask_idx <= src.count:
            water_mask = src.read(mask_idx).astype(bool)

    ndci_array = calculate_ndci(b05_data, b04_data, water_mask=water_mask)

    valid_pixels = ndci_array[~np.isnan(ndci_array)]
    mean_value = float(np.mean(valid_pixels)) if valid_pixels.size > 0 else None

    observation_text = (
        f"Concentración de clorofila-a evaluada (NDCI medio = {mean_value:.2f})"
        if mean_value is not None
        else "No se detectaron píxeles válidos para el cálculo de NDCI."
    )

    schema_result = NdciObservationSchema(
        lake_id=lake_id,
        ndci_value=round(mean_value, 4) if mean_value is not None else None,
        observation=observation_text,
    )

    return ndci_array, schema_result


def _resolve_band_index(
    src: rasterio.DatasetReader,
    band_spec: int | str,
    descriptions: list[str],
    default_idx: int | None,
) -> int:
    """Determina el índice 1-based de una banda según su descripción o número de posición."""
    if isinstance(band_spec, int):
        return band_spec

    spec_str = str(band_spec).upper()
    if spec_str in descriptions:
        return descriptions.index(spec_str) + 1

    if default_idx is not None and default_idx <= src.count:
        return default_idx

    raise ValueError(f"No se pudo determinar el índice para la banda '{band_spec}'")



