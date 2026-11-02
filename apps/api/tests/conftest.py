import importlib.util
import os
from pathlib import Path

rasterio_spec = importlib.util.find_spec("rasterio")
if rasterio_spec is None or rasterio_spec.origin is None:
    raise RuntimeError("Rasterio debe estar instalado para ejecutar los tests del API.")

rasterio_data = Path(rasterio_spec.origin).resolve().parent
gdal_data = rasterio_data / "gdal_data"
proj_data = rasterio_data / "proj_data"

if not gdal_data.is_dir() or not proj_data.is_dir():
    raise RuntimeError("Rasterio no contiene sus directorios de datos GDAL/PROJ.")

os.environ["GDAL_DATA"] = str(gdal_data)
os.environ["PROJ_LIB"] = str(proj_data)
os.environ["PROJ_DATA"] = str(proj_data)
