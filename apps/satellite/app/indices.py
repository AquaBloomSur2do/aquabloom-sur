import numpy as np


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
