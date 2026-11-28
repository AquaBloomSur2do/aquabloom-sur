# Decisión Arquitectónica: Agrupación de Servicios (Sprint 2)

**Fecha:** 28 de Septiembre de 2026
**Autor:** Jaime Levil
**Ticket:** S2-097

## Contexto
Para el Sprint 2 (Piloto Científico), la plataforma AquaBloom Sur debe evolucionar del monolito inicial a una arquitectura de microservicios basada en Flask/FastAPI, detrás del API Gateway, para soportar el procesamiento satelital y de Machine Learning de forma asíncrona.

## Decisión
Se establecen los siguientes límites de despliegue y propiedad de datos:

### 1. API Gateway
- **Rol:** Punto único de entrada HTTP (`/api/v1`) y enrutador.
- **Propietario de Datos:** Ninguno (Stateless).

### 2. Core Service (FastAPI)
- **Módulos:** Identity & Access, Catalog, Ingestion, Dataset.
- **Rol:** Gestión central de identidad (Supabase Auth), operaciones espaciales (PostGIS), ingesta de muestras in-situ y construcción de las versiones inmutables del dataset oficial.
- **Propietario de Datos:** Perfiles, Organizaciones, Lagos, Estaciones, Importaciones, Muestras (Samples), y Definiciones de Dataset.

### 3. Satellite Service (FastAPI)
- **Módulos:** Procesamiento de imágenes (Rasterio/GeoPandas).
- **Rol:** Consulta, validación y registro de escenas Sentinel-2 L2A, y extracción de observaciones espectrales.
- **Propietario de Datos:** Escenas satelitales, máscaras, índices espectrales (almacenados en un esquema de base de datos aislado) y referencias a Supabase Storage.

### 4. Scientific Service (FastAPI)
- **Módulos:** Entrenamiento (scikit-learn/XGBoost), Inferencia, Job Management.
- **Rol:** Validar entradas de estimación, encolar trabajos asíncronos (vía Redis a los Celery Workers) y exponer los resultados y métricas.
- **Propietario de Datos:** Modelos (Model, ModelVersion), Trabajos asíncronos (TrainingRun, Jobs), Métricas y Estimaciones (resultados de inferencia).

## Consecuencias
- Los microservicios no compartirán tablas de base de datos directamente (a excepción de las claves lógicas como UUIDs).
- La comunicación entre el Core y los servicios científicos se hará mediante contratos OpenAPI estrictos a través del Gateway o vía asincronía.

## Evidencia de trazabilidad de resultados científicos (S3-20)

La respuesta de un trabajo puede incluir `traceability_evidence`, validada por el
modelo Pydantic `TraceabilityEvidence` en
`apps/scientific/app/domains/execution/schemas_execution.py`. Para conservar
compatibilidad con trabajos históricos, el campo es opcional; al persistirlo,
se almacena como `result.traceability_evidence` en el JSONB del resultado de
`public.scientific_jobs`. El endpoint de estado lo proyecta como
`traceability_evidence` en la respuesta.

Los cinco identificadores se interpretan así:

| Campo | Identidad que referencia | Contrato |
| --- | --- | --- |
| `job_id` | Trabajo científico (`public.scientific_jobs.id`) | UUID del trabajo aceptado por `/api/v1/executions/`. |
| `scene_id` | Escena catalogada (`satellite.scenes.id`) | UUID de la escena, no su `scene_identifier` externo. Dataset memberships aún usan proveedor + identificador externo; el servicio debe resolverlos a este UUID. |
| `dataset_version_id` | Versión inmutable (`dataset.versions.id`) | UUID de la versión realmente usada, equivalente a `TrainingConfig.version_id`. |
| `model_id` | Modelo/versión exacta usada | Identificador no vacío; se conserva como texto porque `EstimationConfig.model_id` es texto y no hay aún una tabla de modelos con FK. Debe identificar una versión inmutable, no un alias mutable. |
| `processing_id` | Intento individual de procesamiento | UUID distinto del trabajo; permite distinguir reintentos del mismo `job_id`. No existe hoy una tabla de intentos, por lo que queda registrado dentro de la evidencia JSONB. |

Ejemplo de `result` almacenado y de la evidencia devuelta en el estado del
trabajo:

```json
{
  "processed_pixels": 102400,
  "traceability_evidence": {
    "job_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "scene_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "dataset_version_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "model_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "processing_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
  }
}
```

El ejemplo ilustra la forma del JSON; sus identificadores no documentan una
ejecución real ni afirman una métrica de precisión.

La API ya valida y expone la evidencia persistida. El proceso científico actual
no genera todavía estos cinco valores: en particular, `EstimationConfig.scene_id`
es hoy texto libre, no exige `dataset_version_id`, y no se persiste un UUID por
intento. Por tanto, los productores solo deben adjuntar evidencia cuando hayan
resuelto la escena y utilizado efectivamente la versión/modelo identificados;
el siguiente paso de integración es crear esos identificadores durante el
procesamiento y persistirlos junto al resultado. No se infieren identificadores
ni se presenta evidencia ficticia para resultados existentes.

## Procedencia y límites de entrenamiento (S2-191)

Al completar un entrenamiento, `result.provenance` conserva la procedencia
devuelta por Core para la versión publicada realmente consumida: dataset,
`version_id`, número de versión, checksum del manifiesto, fuentes y clasificación
`synthetic`, `real`, `mixed` o `unknown`. Una consulta de procedencia fallida o
una versión distinta de la solicitada impide completar el trabajo, para evitar
resultados exitosos sin evidencia verificable. `real` significa únicamente que
las fuentes del manifiesto no están marcadas como sintéticas; no es una
verificación independiente de autenticidad.

El resultado también conserva la línea base, MAE/RMSE calculados sobre una
partición secuencial del mismo dataset, tamaños de muestra y metadatos de
reproducibilidad (versión del dataset, configuración, código y entorno). Sus
limitaciones explicitan el uso de datos sintéticos cuando aplica, la falta de
validación independiente con mediciones de campo y que no se calculó `accuracy`
contra valores de referencia independientes. MAE/RMSE no deben presentarse como
una medición de precisión independiente.

Este cambio cubre la implementación técnica, los contratos entre servicios y la
validación automatizada; sin servicios activos desplegados en este flujo, no se
inventan identificadores ni resultados ficticios. Antes de dar por cerrado
`S2-191` en Linear, se debe ejecutar la demostración sobre un entorno activo con
una versión publicada cuyo manifiesto identifique las fuentes, consultar el
estado del trabajo y registrar la evidencia real observada (`job_id`,
`dataset_id`, `version_id`, `origin`, `manifest_checksum`, `MAE`/`RMSE`,
tamaños de partición y limitaciones científicas detectadas).
## Datos mínimos del informe piloto (S3-09)

Todo resultado de entrenamiento piloto incluye el objeto `result.pilot_report`,
validado por el esquema `PilotReport` en
`apps/scientific/app/domains/execution/schemas_execution.py` y documentado en
`contracts/openapi/scientific.yaml`. El contrato exige cuatro secciones
obligatorias de nivel superior:

- `method`: algoritmo, estrategia, variable objetivo, partición (`split_strategy`, `split_ratio`), configuración y entorno de ejecución.
- `results`: predicción puntual, vector de predicciones, métricas (`mae`, `rmse`) y tamaños de muestra de entrenamiento y validación.
- `limitations`: lista no vacía de limitaciones metodológicas explícitas del experimento piloto.
- `provenance`: vínculos de origen que identifican obligatoriamente `dataset_version_id` y `manifest` (`manifest_checksum` SHA-256 y `sources`).

Ejemplo de `pilot_report` válido:

```json
{
  "method": {
    "model": "baseline",
    "strategy": "mean_clorofila_a",
    "target_variable": "clorofila_a",
    "split_strategy": "sequential",
    "split_ratio": 0.8,
    "configuration": {
      "algorithm": "baseline"
    },
    "code_version": "dev",
    "environment": "test"
  },
  "results": {
    "prediction_value": 15.0,
    "predictions": [15.0],
    "metrics": {
      "mae": 15.0,
      "rmse": 15.0
    },
    "train_sample_count": 2,
    "validation_sample_count": 1
  },
  "limitations": [
    "Modelo baseline de referencia basado en la media de clorofila_a de entrenamiento; no incorpora variables espectrales ni espaciales."
  ],
  "provenance": {
    "dataset_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "dataset_version_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "model_version_id": null,
    "manifest": {
      "manifest_checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "storage_path": "datasets/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/v1/manifest.json",
      "sources": [
        "sentinel-2:S2A_MSIL2A_20261120"
      ]
    }
  }
}
```

Ejemplo inválido (rechazado por omitir el campo obligatorio `provenance`):

```json
{
  "method": {
    "model": "baseline",
    "strategy": "mean_clorofila_a",
    "target_variable": "clorofila_a",
    "split_strategy": "sequential",
    "split_ratio": 0.8,
    "configuration": {
      "algorithm": "baseline"
    },
    "code_version": "dev",
    "environment": "test"
  },
  "results": {
    "prediction_value": 15.0,
    "predictions": [15.0],
    "metrics": {
      "mae": 15.0,
      "rmse": 15.0
    },
    "train_sample_count": 2,
    "validation_sample_count": 1
  },
  "limitations": [
    "Modelo baseline de referencia basado en la media de clorofila_a de entrenamiento; no incorpora variables espectrales ni espaciales."
  ]
}
```
