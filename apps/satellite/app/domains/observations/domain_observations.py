from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
import logging
import math
from math import fsum
from pathlib import Path

import numpy as np
import rasterio

from apps.satellite.app.domains.observations.schemas_observations import (
    NdciObservationSchema,
)

logger = logging.getLogger("app.processing")

# Directorio de datos piloto (apps/satellite/data)
DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# --- Constantes y Reglas Temporales (temporal.py) ---

MATCHUP_TEMPORAL_WINDOW_DAYS = 3
MATCHUP_SPATIAL_RADIUS_METERS = 50
MATCHUP_BASE_SRID = 4326

SCENE_PAIR_WINDOW = timedelta(days=5)
ScenePair = tuple[datetime, datetime]


def filter_scene_pairs(
    pairs: Iterable[ScenePair],
    *,
    window: timedelta = SCENE_PAIR_WINDOW,
) -> list[ScenePair]:
    """Keep pairs within the configured window (5 days by default)."""
    if window < timedelta(0):
        raise ValueError("La ventana temporal no puede ser negativa.")

    accepted_pairs = []
    for first_acquired_at, second_acquired_at in pairs:
        if (first_acquired_at.tzinfo is None) != (second_acquired_at.tzinfo is None):
            raise ValueError(
                "Las fechas del par deben usar ambas zona horaria o ninguna."
            )
        if abs(first_acquired_at - second_acquired_at) <= window:
            accepted_pairs.append((first_acquired_at, second_acquired_at))

    return accepted_pairs


# --- Reglas Espaciales Geodésicas (spatial.py) ---


class SpatialThresholdError(ValueError):
    """Excepción lanzada cuando la distancia supera el umbral permitido."""


EARTH_RADIUS_M = 6371000.0


def calculate_wgs84_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calcula la distancia geodésica en metros entre dos puntos (SRID 4326) usando Haversine."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_M * c


def validate_spatial_pair(
    lat1: float, lon1: float, lat2: float, lon2: float, threshold_m: float
) -> float:
    """Evalúa un par de coordenadas y rechaza la operación si la distancia supera el umbral."""
    distance = calculate_wgs84_distance(lat1, lon1, lat2, lon2)

    if distance > threshold_m:
        raise SpatialThresholdError(
            f"El par espacial excede el umbral: {distance:.2f}m > {threshold_m}m."
        )

    return distance


# --- Índices Espectrales: NDWI (indices.py) y NDCI (ndci.py) ---


def calculate_ndwi(
    green_band: np.ndarray | np.ma.MaskedArray,
    nir_band: np.ndarray | np.ma.MaskedArray,
) -> np.ndarray | np.ma.MaskedArray:
    """Calcula el NDWI de McFeeters: (verde - infrarrojo cercano) / (verde + infrarrojo cercano)."""
    if np.ma.isMaskedArray(green_band) or np.ma.isMaskedArray(nir_band):
        green = np.ma.asarray(green_band, dtype=np.float64)
        nir = np.ma.asarray(nir_band, dtype=np.float64)
        denominator = green + nir
        safe_denominator = np.ma.masked_where(denominator == 0, denominator)
        return np.ma.divide(green - nir, safe_denominator)

    green = np.asarray(green_band, dtype=np.float64)
    nir = np.asarray(nir_band, dtype=np.float64)
    numerator = green - nir
    denominator = green + nir
    result = np.full(
        denominator.shape,
        np.nan,
        dtype=np.float64,
    )
    np.divide(numerator, denominator, out=result, where=denominator != 0)
    return result


def calculate_ndci(
    b05: np.ndarray | float,
    b04: np.ndarray | float,
    water_mask: np.ndarray | None = None,
) -> np.ndarray | float:
    """Calcula el Normalized Difference Chlorophyll Index (NDCI) = (B05 - B04) / (B05 + B04)."""
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


def _resolve_band_index(
    src: rasterio.DatasetReader,
    band_spec: int | str,
    descriptions: list[str],
    default_idx: int | None,
) -> int:
    if isinstance(band_spec, int):
        return band_spec

    spec_str = str(band_spec).upper()
    if spec_str in descriptions:
        return descriptions.index(spec_str) + 1

    if default_idx is not None and default_idx <= src.count:
        return default_idx

    raise ValueError(f"No se pudo determinar el índice para la banda '{band_spec}'")


def process_pilot_ndci(
    raster_path: Path | str | None = None,
    lake_id: str = "lago-piloto",
    b04_band: int | str = "B04",
    b05_band: int | str = "B05",
    water_mask_band: int | str | None = "water_mask",
) -> tuple[np.ndarray, NdciObservationSchema]:
    """Lee el raster preparado multi-banda GeoTIFF del piloto y calcula el índice NDCI."""
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


# --- Enmascaramiento de Calidad Ráster (processing.py) ---


def apply_quality_mask(
    raster: np.ndarray | np.ma.MaskedArray,
    valid_mask: np.ndarray,
    *,
    exclusion_masks: Mapping[str, np.ndarray] | None = None,
    nodata_value: float | None = None,
) -> tuple[np.ma.MaskedArray, dict[str, int | dict[str, int]]]:
    """Mask invalid raster pixels and report the count for each exclusion reason."""
    raster_array = np.ma.asarray(raster)
    if raster_array.ndim < 2:
        raise ValueError("El raster debe tener al menos dos dimensiones.")

    raster_data = np.ma.getdata(raster_array)
    if not np.issubdtype(raster_data.dtype, np.number):
        raise TypeError("El raster debe contener valores numéricos.")

    spatial_shape = raster_array.shape[-2:]
    valid_pixels = np.asarray(valid_mask)
    if valid_pixels.shape != spatial_shape or valid_pixels.dtype != np.bool_:
        raise ValueError(
            "La máscara de calidad debe ser booleana y coincidir con las "
            "dimensiones espaciales del raster."
        )

    invalid_pixels = ~valid_pixels
    reason_masks: dict[str, np.ndarray] = {}

    if exclusion_masks is not None:
        for reason, mask in exclusion_masks.items():
            if not reason or reason in {"quality_mask", "nodata"}:
                raise ValueError(f"Motivo de exclusión no válido: {reason!r}.")
            reason_mask = np.asarray(mask)
            if reason_mask.shape != spatial_shape or reason_mask.dtype != np.bool_:
                raise ValueError(
                    f"La máscara para {reason!r} debe ser booleana y coincidir "
                    "con las dimensiones espaciales del raster."
                )
            reason_masks[reason] = reason_mask
            invalid_pixels |= reason_mask

    raster_mask = np.ma.getmaskarray(raster_array)
    if raster_array.ndim > 2:
        raster_mask = np.any(raster_mask, axis=tuple(range(raster_array.ndim - 2)))
    nodata_pixels = raster_mask.copy()
    if np.issubdtype(raster_data.dtype, np.inexact):
        nan_pixels = np.isnan(raster_data)
        if raster_array.ndim > 2:
            nan_pixels = np.any(
                nan_pixels,
                axis=tuple(range(raster_array.ndim - 2)),
            )
        nodata_pixels |= nan_pixels
    if nodata_value is not None and not np.isnan(nodata_value):
        nodata_values = np.equal(raster_data, nodata_value)
        if raster_array.ndim > 2:
            nodata_values = np.any(
                nodata_values,
                axis=tuple(range(raster_array.ndim - 2)),
            )
        nodata_pixels |= nodata_values
    invalid_pixels |= nodata_pixels

    exclusion_reasons = {
        reason: int(np.count_nonzero(mask & invalid_pixels))
        for reason, mask in reason_masks.items()
    }
    exclusion_reasons["nodata"] = int(np.count_nonzero(nodata_pixels))
    explained_pixels = nodata_pixels.copy()
    for reason_mask in reason_masks.values():
        explained_pixels |= reason_mask
    exclusion_reasons["quality_mask"] = int(
        np.count_nonzero(invalid_pixels & ~explained_pixels)
    )

    masked_raster = np.ma.array(
        raster_array,
        mask=np.broadcast_to(invalid_pixels, raster_array.shape),
        copy=True,
    )
    excluded_pixel_count = int(np.count_nonzero(invalid_pixels))
    logger.info(
        "Se excluyeron %d píxeles por calidad: %s",
        excluded_pixel_count,
        exclusion_reasons,
    )

    return masked_raster, {
        "excluded_pixel_count": excluded_pixel_count,
        "exclusion_reasons": exclusion_reasons,
    }


# --- Resumen Estadístico de Mediciones (tasks.py) ---


def summarize_measurements(measurements: list[float]) -> dict[str, int | float]:
    if not measurements:
        raise ValueError("Se requiere al menos una medición.")

    return {
        "count": len(measurements),
        "minimum": min(measurements),
        "maximum": max(measurements),
        "mean": fsum(value / len(measurements) for value in measurements),
    }
    
