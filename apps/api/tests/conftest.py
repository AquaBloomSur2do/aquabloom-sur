import os
from pathlib import Path

import rasterio

rasterio_data = Path(rasterio.__file__).resolve().parent
gdal_data = rasterio_data / "gdal_data"
proj_data = rasterio_data / "proj_data"

if not gdal_data.is_dir() or not proj_data.is_dir():
    raise RuntimeError("Rasterio no contiene sus directorios de datos GDAL/PROJ.")

os.environ["GDAL_DATA"] = str(gdal_data)
os.environ["PROJ_LIB"] = str(proj_data)
os.environ["PROJ_DATA"] = str(proj_data)
