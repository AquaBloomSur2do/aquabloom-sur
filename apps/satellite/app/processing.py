import logging
from collections.abc import Mapping

import numpy as np

logger = logging.getLogger(__name__)


def apply_quality_mask(
    raster: np.ndarray | np.ma.MaskedArray,
    valid_mask: np.ndarray,
    *,
    exclusion_masks: Mapping[str, np.ndarray] | None = None,
    nodata_value: float | None = None,
) -> tuple[np.ma.MaskedArray, dict[str, int | dict[str, int]]]:
    """Mask invalid raster pixels and report the count for each exclusion reason.

    The quality mask and exclusion masks use True to indicate valid and invalid
    pixels, respectively. For rasters with bands, spatial dimensions are the
    final two axes and any invalid band masks the entire pixel. Per-reason
    counts are independent, so overlapping reasons can count the same pixel.
    """
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
