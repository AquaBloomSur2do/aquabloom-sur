# Política de retención de resultados piloto (S3-18)

## Alcance y estado actual

Esta política se aplica a los trabajos creados por `/api/v1/executions/` y por
el puente del Gateway `/api/v1/executions/jobs`. Ambos invocan
`create_execution_job_service`; el trabajo se ejecuta con `BackgroundTasks` en
el proceso FastAPI, no en la cola Redis de `measurement-summary`. El código
dirige la persistencia a `public.scientific_jobs`.

**Discrepancia de esquema que debe verificarse en el entorno:** el código
escribe `dataset_version_id` en `public.scientific_jobs`, y `JobStatus` también
lo modela. Sin embargo, la migración `022_scientific_jobs_idempotency.sql` no
crea esa columna; la migración `019_create_scientific_jobs_table.sql` la crea
en otra tabla, `scientific.jobs`. Por tanto, las migraciones versionadas aquí
no bastan para garantizar que un entrenamiento complete su inserción y
actualización en `public.scientific_jobs`: el servicio agrega el campo al
payload de inserción y luego a la actualización de finalización. Aplicar solo
las migraciones del repo puede hacer que PostgREST rechace la inserción del
trabajo. La política no supone que exista una migración externa: el operador
debe comprobar el esquema desplegado antes de considerar operativa la retención
de entrenamientos.

El repositorio no define un plazo de retención, una tarea programada de
limpieza, una papelera, ni un endpoint de borrado para esos trabajos. Por tanto,
la retención de la fila y de los datos de Storage es indefinida mientras no se
apruebe una limpieza manual para el piloto. La limpieza descrita aquí es una
regla operativa; no está automatizada por la aplicación.

## Qué se retiene

| Dato | Capa y campos reales | Regla |
| --- | --- | --- |
| Registro del trabajo | PostgreSQL/Supabase, `public.scientific_jobs`: `id`, `organization_id`, `requested_by`, `job_type`, `status`, `config`, `result`, `error_message`, `idempotency_key`, `created_at`, `updated_at`, `started_at`, `completed_at`, `model_version_id` y `scene_id`. El código también espera/escribe `dataset_version_id`, pero esa columna no está en la migración de `public.scientific_jobs` del repositorio (ver discrepancia arriba). | Retener la fila completa durante el piloto y hasta que el responsable autorice su cierre. En la API `JobStatus.id` se serializa con el alias `job_id`; la columna persistida sigue llamándose `id`. No asumir que `dataset_version_id` persiste sin verificar el esquema desplegado. |
| Resultado y reproducibilidad de entrenamiento | `scientific_jobs.result` (JSONB), serializado desde `TrainingResult`: `model`, `baseline`, `prediction_value`, `predictions`, `metrics`, `version`, `dataset_version_id`, `model_version_id`, `reproducibility`, `status` y `warnings`. `reproducibility` contiene `dataset_version_id`, `partition` (`strategy`, `split_ratio`, `train_sample_count`, `validation_sample_count`), `seed`, `configuration`, `code_version` y `environment`. | Retener el resultado completo y sus métricas. El entrenamiento actual usa partición secuencial 80/20 y `seed: null`; no se debe reconstruir ni sustituir esta evidencia por logs. |
| Datos de entrada versionados | Esquema `dataset`: `versions`, `training_manifests` y el CSV referenciado por `training_manifests.storage_path` en el bucket privado `training_files`. El manifiesto registra `version_id`, `storage_path`, `checksum`, `variables` y `created_at`. | No purgar una versión, su manifiesto o su archivo mientras un resultado retenido dependa de `dataset_version_id`. El trabajador verifica el SHA-256 del CSV antes de procesarlo. |
| Referencias de modelo/escena, cuando aplican | `scientific_jobs.model_version_id` y `scientific_jobs.scene_id`; para entrenamiento, `config.version_id` y los `dataset_version_id` que aparecen en el resultado. La columna superior `scientific_jobs.dataset_version_id` la escribe el código, pero no está creada por la migración de la tabla pública. Para estimación, `result` incluye `model_id`, `scene_id`, `model_type`, `artifact_checksum`, `point_count` y `predictions`. | Retener los UUID de origen y los registros referenciados mientras se conserve el trabajo. No borrar escenas referenciadas: la FK de `scene_id` usa `ON DELETE RESTRICT`. |
| Resultados de estimación guardados por el flujo de predicciones | Separadamente, `scientific.predictions`: `id`, `organization_id` (agregado por migración), `model_version_id`, `scene_id`, `result`, `rules` y `created_at`. | Es un registro distinto: la tabla no tiene `job_id` y no se debe tratar como parte de una limpieza de `scientific_jobs`. Retenerlo según su propia decisión de piloto; la FK a escena también usa `ON DELETE RESTRICT`. |
| Correlación y logs | `X-Correlation-ID` se devuelve en la respuesta y aparece como `correlation_id` en los logs de inicio/finalización/error. No es una columna de `scientific_jobs` ni parte de `JobStatus`. | Mantener los logs según la política del entorno. Antes de eliminarlos, el operador debe copiar manualmente el valor de correlación junto a `job_id` y `organization_id` en el registro de auditoría aprobado para el piloto. Esa captura no la realiza el código de AquaBloom Sur. |

`TraceabilityEvidence` no está definido en los esquemas ni se persiste en el
flujo actual. La evidencia disponible para entrenamiento es la fila del trabajo,
`result.reproducibility` y el vínculo a la versión/manifiesto del dataset. El
checksum del archivo está en `dataset.training_manifests`; no se incluye
automáticamente como campo de `TrainingResult`.

El módulo `model_artifacts.py` ofrece `save_model_artifact`, que puede añadir
`result.model_artifact` con `job_id`, `bucket`, `storage_path`, `checksum` y
`size_bytes`. Sin embargo, el flujo actual de `process_scientific_job` no llama
a ese helper y las migraciones revisadas no crean el bucket `model_artifacts`.
Por tanto, no se considera un artefacto producido por defecto ni se debe
presuponer que exista. Si una ejecución concreta sí tiene ese objeto, conservar
tanto la referencia como el archivo del bucket hasta que se apruebe su limpieza.

## Qué puede limpiarse y procedimiento

La limpieza solo se autoriza al cerrar o depurar un piloto, con aprobación del
responsable de los datos y después de comprobar que se conservaron los campos y
vínculos descritos en esta política. No hay un período numérico configurado en
el repositorio: la decisión es manual y debe considerar los compromisos de
retención externos que apliquen.

| Elemento | Qué ocurre hoy | Regla de limpieza |
| --- | --- | --- |
| Copias de trabajo en memoria | El servicio descarga el CSV y crea bytes, filas y resultados en memoria durante la llamada. No crea una copia temporal persistente en disco. | Al terminar la función, esos objetos dejan de ser parte del resultado persistido; no requieren una tarea de borrado de archivos. No confundirlos con el CSV oficial en `training_files`. |
| Cola Redis `scientific:tasks` | Corresponde a `measurement-summary`, no a `/api/v1/executions`. El productor encola mediciones y `BRPOP` retira el mensaje al consumirlo; el resumen solo se escribe en logs, no se guarda en PostgreSQL. `compose.yaml` no declara opciones de persistencia ni volumen y no hay TTL configurado por la aplicación. | No usarla como archivo de trabajos o resultados. Si quedan mensajes y el operador decide descartarlos, inspeccionar esa cola concreta y purgarla manualmente; no ejecutar un vaciado general de Redis ni asumir que un mensaje contiene un `job_id` de ejecución. |
| Logs del proceso/API/worker | Se emiten al logger; la configuración de retención/rotación depende del entorno de ejecución y no está definida por el repositorio. | No eliminar la única copia del `correlation_id` antes de registrarlo manualmente junto con `job_id` y `organization_id` en el registro de auditoría del piloto. La conservación de logs no sustituye a la fila de base de datos. |
| Fila `public.scientific_jobs` y su JSON `config`/`result` | Persistencia permanente de aplicación; no existe endpoint o tarea de limpieza. | No eliminar ni recortar el JSON como limpieza rutinaria: `config` contiene la solicitud y `result` contiene métricas, predicciones y reproducibilidad. Una eliminación excepcional es manual y debe conservar previamente el registro mínimo requerido en un medio de auditoría aprobado. |
| CSV/manifiesto de la versión de dataset | Son entradas versionadas reutilizables, no temporales creados por cada ejecución. | No borrar como parte de la limpieza de un solo trabajo. Evaluar la versión, el manifiesto y el archivo en conjunto y solo tras comprobar que ningún otro trabajo retenido depende de ellos. |
| Artefacto `model_artifact` opcional | Solo existe si un llamador usa explícitamente `save_model_artifact`; no lo genera el flujo actual de ejecución por defecto. | Si existe, comprobar primero todas las referencias antes de eliminar el objeto de Storage. No dejar una referencia `model_artifact` apuntando a un objeto purgado. |
| `scientific.predictions` | Es una persistencia separada, no enlazada por `job_id`. | No incluir sus filas en una limpieza de trabajos; requiere decisión y verificación independientes. |

Para una purga manual de un registro, el responsable debe identificar la fila por
`id` y `organization_id`, verificar que el trabajo no está en curso y que el
resultado/evidencia requerida ya fue conservado, y comprobar sus referencias
antes de operar directamente en la base de datos o Storage con credenciales
autorizadas. No se debe borrar una organización como método de limpieza: la FK
de `organization_id` en `public.scientific_jobs` tiene `ON DELETE CASCADE` y
eliminaría sus trabajos. `requested_by` puede quedar en `NULL` al eliminar al
usuario, por su FK `ON DELETE SET NULL`; por ello no es un sustituto de
`organization_id` ni de `job_id`.

## Referencias mínimas que deben sobrevivir

Para cualquier resultado retenido, mantener juntos:

- `scientific_jobs.id` (el mismo identificador que la respuesta expone como
  `job_id`) y `organization_id`.
- `job_type`, `status`, `created_at`, `started_at`, `completed_at` y, si
  corresponde, `error_message`.
- `config` y `result` completos mientras el objetivo sea preservar la
  reproducibilidad de la ejecución.
- Los vínculos aplicables: `config.version_id`; `model_version_id` y
  `scene_id`; además de `result.dataset_version_id`,
  `result.reproducibility.dataset_version_id` y `result.model_artifact` cuando
  existan. La columna de nivel superior `dataset_version_id` solo puede
  considerarse persistida tras verificar que la instalación la tiene.
- `idempotency_key` cuando se haya enviado; es opcional, pero forma parte de la
  fila y su índice único es por `organization_id`.
- `X-Correlation-ID` mediante el registro manual indicado arriba si se exige
  que sobreviva a la eliminación/rotación de logs. Actualmente no hay una
  referencia persistida en DB que permita recuperarlo después.

Los UUID de dataset, modelo y escena solo son referencias útiles si los
registros de origen y, para entrenamiento, el manifiesto/archivo necesario
siguen disponibles. No hay un esquema llamado `TraceabilityEvidence`; no se
debe declarar que existe una evidencia de ese tipo.

## Ejemplo ficticio de una ejecución antes y después

El ejemplo representa un entrenamiento completado con diez mediciones
sintéticas de `clorofila_a`: las primeras ocho tienen media `5.0` y las dos de
validación son `6.0` y `8.0`. El baseline predice `[5.0, 5.0]`, por lo que
`mae = 2.0` y `rmse = 2.23606797749979`. Los UUID, checksum y valores son datos
de prueba, no identificadores ni credenciales reales.

### Antes de la limpieza

Ejemplo de fila y resultado que el flujo de entrenamiento intenta guardar en
`public.scientific_jobs` (se omiten solo campos que no son relevantes). La
columna superior `dataset_version_id` refleja el payload generado por el
código; como se indicó arriba, solo queda persistida en un entorno cuyo esquema
la tenga provisionada. Si el entorno usa únicamente las migraciones del repo,
no se debe interpretar este JSON como evidencia de que el entrenamiento haya
completado correctamente:

```json
{
  "id": "a418ad18-1595-4db8-ae78-4e7924d35bf0",
  "organization_id": "ea67a33e-9694-4e8f-aad8-5d055f1c89ab",
  "requested_by": "b9c50de9-9b86-47ef-8c43-5089dd7b3151",
  "job_type": "training",
  "status": "completed",
  "idempotency_key": "pilot-s3-18-run-001",
  "config": {
    "dataset_id": "0df21491-9b94-4f41-84a4-4d3e2d9e59c0",
    "version_id": "1b603793-0d67-4a82-97a3-27eb8bc09ab4",
    "epochs": 100,
    "learning_rate": 0.001
  },
  "dataset_version_id": "1b603793-0d67-4a82-97a3-27eb8bc09ab4",
  "model_version_id": null,
  "scene_id": null,
  "error_message": null,
  "created_at": "2026-10-12T10:00:00Z",
  "started_at": "2026-10-12T10:00:01Z",
  "completed_at": "2026-10-12T10:00:02Z",
  "updated_at": "2026-10-12T10:00:02Z",
  "result": {
    "model": "baseline",
    "baseline": {
      "strategy": "mean_clorofila_a",
      "target_variable": "clorofila_a",
      "prediction_value": 5.0,
      "train_sample_count": 8,
      "validation_sample_count": 2
    },
    "prediction_value": 5.0,
    "predictions": [5.0, 5.0],
    "metrics": {
      "mae": 2.0,
      "rmse": 2.23606797749979
    },
    "version": "1b603793-0d67-4a82-97a3-27eb8bc09ab4",
    "dataset_version_id": "1b603793-0d67-4a82-97a3-27eb8bc09ab4",
    "model_version_id": null,
    "reproducibility": {
      "dataset_version_id": "1b603793-0d67-4a82-97a3-27eb8bc09ab4",
      "partition": {
        "strategy": "sequential",
        "split_ratio": 0.8,
        "train_sample_count": 8,
        "validation_sample_count": 2
      },
      "seed": null,
      "configuration": {
        "algorithm": "baseline",
        "baseline_strategy": "mean_clorofila_a",
        "training_config": {
          "dataset_id": "0df21491-9b94-4f41-84a4-4d3e2d9e59c0",
          "version_id": "1b603793-0d67-4a82-97a3-27eb8bc09ab4",
          "epochs": 100,
          "learning_rate": 0.001
        },
        "split_strategy": "sequential",
        "split_ratio": 0.8
      },
      "code_version": "staging-local",
      "environment": "staging"
    },
    "status": "completed",
    "warnings": [
      "Modelo baseline de referencia basado en la media de clorofila_a de entrenamiento; no incorpora variables espectrales ni espaciales.",
      "Tamaño de muestra reducido (entrenamiento=8, validación=2); interpretar métricas con precaución."
    ]
  }
}
```

La versión usada sigue apuntando a su fila `dataset.training_manifests`. Para
que el ejemplo del insumo sea verificable, el CSV UTF-8 de prueba (incluida la
última línea nueva) es:

```csv
clorofila_a
4
4
4
4
6
6
6
6
6
8
```

Su fila ficticia de manifiesto en `dataset.training_manifests` es:

```json
{
  "id": "d27dcc64-4636-477d-94d2-d2b112e111a6",
  "version_id": "1b603793-0d67-4a82-97a3-27eb8bc09ab4",
  "storage_path": "pilot/s3-18/training.csv",
  "checksum": "e5dd5cffade5d81038ee910e7530d1d54961fcedf972da46000c0c33a4c04d63",
  "variables": ["temperatura", "clorofila_a", "turbidez", "ph"],
  "created_at": "2026-10-12T09:59:00Z"
}
```

Ese SHA-256 corresponde exactamente al contenido CSV anterior. El archivo vive
en el bucket privado `training_files`. La ejecución usó
además el `X-Correlation-ID: pilot-s3-18-corr-001`, visible en sus logs, pero
ese valor no está en la fila JSON anterior. Los bytes descargados y las filas
parseadas fueron datos en memoria; no se creó un archivo temporal de ejecución
ni una entrada en Redis para este `job_id`.

### Después de limpiar los temporales de ejecución

La fila `scientific_jobs`, incluidos `config`, `result` y todos los UUID,
permanece igual que antes. Se conserva también el manifiesto y el CSV de la
versión publicada. Los bytes/filas de trabajo ya no son una copia persistente;
no hay una clave Redis de este trabajo que borrar. Antes de retirar los logs,
el operador copia manualmente esta relación en el registro de auditoría
aprobado para el piloto:

| Referencia conservada | Valor de prueba | Capa |
| --- | --- | --- |
| `job_id` (columna `id`) | `a418ad18-1595-4db8-ae78-4e7924d35bf0` | `public.scientific_jobs` y registro de auditoría |
| `organization_id` | `ea67a33e-9694-4e8f-aad8-5d055f1c89ab` | `public.scientific_jobs` y registro de auditoría |
| `dataset_version_id` | `1b603793-0d67-4a82-97a3-27eb8bc09ab4` | `config.version_id`, resultado, reproducibilidad y manifiesto; columna superior solo si existe en el esquema desplegado |
| Estado/resultado final | `completed`, métricas, predicciones y `reproducibility` mostrados arriba | `public.scientific_jobs.result` |
| `X-Correlation-ID` / `correlation_id` | `pilot-s3-18-corr-001` | Logs hasta captura; luego registro manual de auditoría |

Así, la limpieza ejemplificada no borra el trabajo ni la evidencia de
reproducibilidad. El registro manual de correlación es una acción exigida por
esta política, no una persistencia que ya implemente la aplicación.

## Fuentes de implementación

- [Puente del Gateway](../apps/api/app/gateway/executions_bridge.py),
  [ejecuciones científicas](../apps/scientific/app/domains/execution/service_execution.py),
  [controlador](../apps/scientific/app/domains/execution/controller_execution.py),
  [esquemas](../apps/scientific/app/domains/execution/schemas_execution.py) y
  [persistencia](../apps/scientific/app/domains/execution/model_execution.py).
- [Correlación](../apps/scientific/app/core/correlation.py),
  [artefactos de modelo](../apps/scientific/app/domains/execution/model_artifacts.py),
  [predicciones](../apps/scientific/app/domains/prediction/model_prediction.py) y
  [Compose](../compose.yaml).
- [Worker Redis](../apps/scientific/app/worker.py),
  [cola Satellite](../apps/satellite/app/core/queueing.py) y
  [documentación del worker](./scientific-worker.md).
- [Versiones y manifiestos de datasets](./dataset-versioning.md),
  [migración de manifiestos](../database/migrations/018_create_training_manifests.sql),
  [tabla científica anterior](../database/migrations/019_create_scientific_jobs_table.sql),
  [migración de trabajos](../database/migrations/022_scientific_jobs_idempotency.sql),
  [alcance organizacional](../database/migrations/023_scientific_jobs_organization_scope.sql),
  [referencias de estimación](../database/migrations/027_link_estimation_jobs.sql) y
  [resultados de predicción](../database/migrations/025_create_scientific_predictions.sql),
  [alcance organizacional de predicciones](../database/migrations/026_add_organization_scope_to_scientific_predictions.sql).
