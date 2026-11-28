# Registro Revisable de Procedencia del Insumo Sentinel-2 (`S3-03`)

**Fecha de verificación:** 26 de noviembre de 2026  
**Commit de referencia:** `f082c02`  
**Insumo auditado:** `AQU-154` (`[S2-100] Preparar el insumo satelital de prueba`)  
**Fuentes de verdad:** `apps/satellite/data/pilot_sentinel2_l2a.tif`, `apps/satellite/data/metadata.json`, `apps/satellite/scripts/prepare_pilot_data.py`, `apps/satellite/app/domains/observations/domain_observations.py` y `apps/api/app/domains/dataset/service_dataset.py`

---

## 1. Resumen de Verificación

Se verificó la integridad criptográfica, la estructura espacial, la máscara de agua y el cálculo del índice **NDCI** sobre el insumo satelital preparado en `S2-100`.

- **Naturaleza del insumo:** **Sintético** (`is_synthetic: true`, `provenance: "Synthetic Sentinel-2 L2A Pilot"`), generado de forma determinista por `apps/satellite/scripts/prepare_pilot_data.py` con semilla `20250115`. No corresponde a un producto real descargado de Copernicus Sentinel-2 y **no representa mediciones reales de un lago**.
- **Integridad SHA-256:** Verificada sin discrepancias (`sha256_match = True`) entre `pilot_sentinel2_l2a.tif` y el campo `sha256` de `metadata.json`.
- **Consistencia de máscara y NDCI:** Los 4.513 píxeles marcados como agua (`water_mask == 1`) producen 4.513 valores finitos de NDCI (`NDCI medio = 0.163795`, redondeado a `0.1638` por `process_pilot_ndci`), mientras los 5.487 píxeles inválidos (`water_mask == 0`) quedan excluidos (`NaN`).

---

## 2. Registro Maestro de Vinculación (`S2-100` → Escena, Fecha, Máscara y NDCI)

| Dimensión | Campo / Evidencia | Valor Verificado en `f082c02` | Origen Técnico |
| --- | --- | --- | --- |
| **Insumo (`S2-100`)** | Archivo raster | `apps/satellite/data/pilot_sentinel2_l2a.tif` (`31.042` bytes) | `apps/satellite/scripts/prepare_pilot_data.py` |
| **Integridad Raster** | SHA-256 (archivo vs. metadatos) | `f352bd259ef620e0a78ff6ef39e0ba0a331e2d4d49770f048ddf791e8e4af095` (**Coincide**) | `sha256sum` / `metadata.json` |
| **Metadatos** | Archivo y SHA-256 | `apps/satellite/data/metadata.json` (`1.116` bytes) — `2ba05ceed406b639f16138d5a52f2524360e0320848fc05b71ff5fcd459be4b7` | `apps/satellite/data/metadata.json` |
| **Escena** | `id` / `scene_identifier` | `pilot_sentinel2_l2a` / `SYNTHETIC_SENTINEL2_L2A_PILOT_20250115` | `metadata.json` (`pilot_fixture`) |
| **Proveedor y Origen** | `provider` / `is_synthetic` | `Sentinel-2` / `true` (`Synthetic Sentinel-2 L2A Pilot`, `dataset_version: pilot-fixture-v1`, `random_seed: 20250115`) | `metadata.json` (`pilot_fixture`) |
| **Fecha** | `acquisition_date` | `2025-01-15` (ISO 8601) | `metadata.json` (`DEFAULT_ACQUISITION_DATE`) |
| **Máscara** | Banda 3 (`water_mask`) | `4.513` píxeles de agua (`1`, `45.13%`) y `5.487` píxeles excluidos (`0`, `54.87%`); `0` valores fuera de dominio | `pilot_sentinel2_l2a.tif` (banda 3) |
| **Índice NDCI** | $\text{NDCI} = \frac{B05 - B04}{B05 + B04}$ | `4.513` píxeles válidos; media `0.163795` (`0.1638`), mediana `0.163724`, mín `0.149713`, máx `0.181014`, DE `0.005582` | `domain_observations.py` (`calculate_ndci` / `process_pilot_ndci`) |

---

## 3. Especificación Técnica del Raster y Generación Reproducible

### 3.1 Propiedades Espaciales y de Formato

| Parámetro | Valor Verificado | Observación |
| --- | --- | --- |
| Formato / Compresión | GeoTIFF (`GTiff`), compresión `deflate` | Verificado vía `rasterio` |
| Bandas y tipo de dato | `3` bandas (`uint16`, `uint16`, `uint16`) | Descripciones embebidas: `B04`, `B05`, `water_mask` |
| Dimensiones | `100 × 100` píxeles (`10.000` píxeles totales) | Resolución espacial `10 m × 10 m` (`1 km²`) |
| Sistema de referencia (CRS) | `EPSG:32718` (UTM Zona 18S) | Coherente con la zona piloto en el sur de Chile |
| Extensión (`bounds`) | `left=700000.0`, `bottom=5699000.0`, `right=701000.0`, `top=5700000.0` | Transformación GDAL: `[700000.0, 10.0, 0.0, 5700000.0, 0.0, -10.0]` |
| Factor de escala de reflectancia | `reflectance_scale = 10000` | Declarado en `metadata.json` |

### 3.2 Definición de Bandas y Máscara de Agua (`prepare_pilot_data.py`)

El insumo fue generado mediante `generate_pilot_data` con semilla fija `20250115` (`np.random.default_rng(20250115)`):

- **Banda 1 (`B04` — Rojo, 665 nm simulado):** gradiente determinista `900 + col * 3 + row * 2` más ruido entero uniforme en `[-10, 10]`. Sobre píxeles de agua escalados por `10000`: mínimo `0.1005`, media `0.114997`, máximo `0.1291`.
- **Banda 2 (`B05` — Red Edge, 705 nm simulado):** gradiente determinista `1300 + col * 4 + row * 2` más ruido entero uniforme en `[-10, 10]`. Sobre píxeles de agua escalados por `10000`: mínimo `0.1424`, media `0.159990`, máximo `0.1774`.
- **Banda 3 (`water_mask`):** máscara binaria circular centrada en `(50, 50)` con radio `38` píxeles (`(col - 50)^2 + (row - 50)^2 <= 38^2`):
  - `1` (`water`): `4.513` píxeles (`45.13%`).
  - `0` (`invalid`): `5.487` píxeles (`54.87%`).
  - Otros valores: `0` píxeles (`0.00%`).

---

## 4. Verificación del Cálculo de NDCI y Relación con Manifiestos

### 4.1 Fórmula y Comportamiento de `domain_observations.py`

El cálculo de NDCI se ejecuta en `apps/satellite/app/domains/observations/domain_observations.py`:

$$\text{NDCI} = \frac{B05 - B04}{B05 + B04}$$

1. `process_pilot_ndci()` resuelve los índices de banda por nombre (`B04` → 1, `B05` → 2, `water_mask` → 3), convierte la banda 3 a booleana (`1 → True`, `0 → False`) e invoca `calculate_ndci(b05_data, b04_data, water_mask=water_mask)`.
2. `calculate_ndci()` convierte `B05` y `B04` a `float64` antes de restar (evitando desbordamiento *unsigned* de `uint16`), protege divisiones por cero (`NaN` si `B05 + B04 == 0`) y enmascara a `NaN` todo píxel donde `water_mask` es `False`.
3. Aunque `process_pilot_ndci()` opera sobre los valores `uint16` sin dividir explícitamente por `reflectance_scale` (`10000`), el índice NDCI es una razón normalizada invariante ante un factor de escala positivo constante ($s = 10000$ se cancela entre numerador y denominador), arrojando exactamente los mismos estadísticos.

### 4.2 Resultados Estadísticos Verificados sobre Píxeles de Agua

| Métrica NDCI | Valor Obtenido |
| --- | --- |
| Píxeles válidos evaluados | `4.513` (`0` descartados por denominador nulo) |
| Mínimo | `0.149713` |
| Media | `0.163795` (`0.1638` en `NdciObservationSchema.ndci_value`) |
| Mediana | `0.163724` |
| Máximo | `0.181014` |
| Desviación estándar | `0.005582` |

### 4.3 Propagación de Procedencia hacia Datasets (`Core`)

En `apps/api/app/domains/dataset/service_dataset.py` (`build_version_manifest_service`), el servicio Core lee `apps/satellite/data/metadata.json` para propagar `id`, `provider`, `is_synthetic`, `sha256` y `pilot_fixture` hacia el manifiesto de versión del dataset (`DatasetManifest` / `DatasetProvenance`).

---

## 5. Evidencia de Verificación Ejecutada

### 5.1 Pruebas Automatizadas Ejecutadas

```bash
PYTHONPATH=. python -m pytest \
  apps/satellite/tests/test_prepare_pilot_data.py \
  apps/satellite/tests/test_ndci.py -q
```

- **Resultado observado:** `9 passed in 1.15s`.

### 5.2 Comando Reproducible de Auditoría de Integridad, Máscara y NDCI

```bash
sha256sum apps/satellite/data/pilot_sentinel2_l2a.tif apps/satellite/data/metadata.json

PYTHONPATH=. python -c "
import hashlib, json
from pathlib import Path
import numpy as np
import rasterio

data_dir = Path('apps/satellite/data')
meta = json.loads((data_dir / 'metadata.json').read_text(encoding='utf-8'))
tif_path = data_dir / meta['raster_file']
actual_sha = hashlib.sha256(tif_path.read_bytes()).hexdigest()

with rasterio.open(tif_path) as src:
    b04 = src.read(meta['bands']['B04']).astype(np.float64) / meta['reflectance_scale']
    b05 = src.read(meta['bands']['B05']).astype(np.float64) / meta['reflectance_scale']
    mask = src.read(meta['bands']['water_mask'])
    water = mask == meta['water_mask_values']['water']
    denom = b05 + b04
    valid = water & (denom != 0)
    ndci = (b05[valid] - b04[valid]) / denom[valid]

print('sha256_match:', actual_sha == meta['sha256'])
print('water_pixels:', int(water.sum()), 'invalid_pixels:', int((~water).sum()))
print('ndci_mean:', round(float(ndci.mean()), 6), 'ndci_min:', round(float(ndci.min()), 6), 'ndci_max:', round(float(ndci.max()), 6))
"
```

---

## 6. Limitaciones Científicas y Brechas de Trazabilidad Detectadas

| Hallazgo | Situación Actual en `f082c02` | Impacto / Acción Recomendada en Sprint 3 |
| --- | --- | --- |
| **Origen sintético sin producto Copernicus real** | El raster de `S2-100` es 100% sintético (`is_synthetic: true`), sin granularidad real (`SAFE`/tile ID real) ni banda `SCL` de clasificación de nubes/sombras de Sentinel-2 L2A. | Mantener la etiqueta `synthetic` en toda demostración y reemplazar por una escena real verificada de Sentinel-2 L2A cuando se valide un lago piloto con datos observacionales. |
| **Sin verificación de SHA-256 ni metadatos en `process_pilot_ndci`** | `process_pilot_ndci()` lee directamente `pilot_sentinel2_l2a.tif` sin contrastar su SHA-256 contra `metadata.json` y devuelve `NdciObservationSchema(lake_id, ndci_value, observation)` sin `scene_identifier`, `acquisition_date`, `sha256` ni `is_synthetic`. | Incorporar verificación opcional/obligatoria de integridad contra `metadata.json` y adjuntar metadatos de escena y procedencia en la salida de observaciones NDCI. |
| **Sin vínculo persistido a `satellite.scenes.id`** | `metadata.json` declara `scene_identifier: SYNTHETIC_SENTINEL2_L2A_PILOT_20250115` y `acquisition_date: 2025-01-15`, pero no referencia