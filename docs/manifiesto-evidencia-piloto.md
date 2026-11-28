# Manifiesto de evidencia del piloto (S3-44)

El ejemplo [manifiesto-evidencia-piloto.ejemplo.json](./examples/manifiesto-evidencia-piloto.ejemplo.json)
es un sobre de referencias sintéticas para enlazar un dataset y su versión, una
escena, un modelo y una ejecución. Todos los UUID y valores del archivo son de
prueba: no representan registros ni resultados reales y el manifiesto no los
crea en la base de datos.

Su estructura exige `manifest_version`, `synthetic` y los cuatro objetos:
`dataset`, `scene`, `model` y `execution`. Los campos mínimos de cada objeto
son:

| Entidad | Identificador estable | Metadatos incluidos |
| --- | --- | --- |
| `dataset` | `dataset_id` y `dataset_version_id` (UUID); `version_number` permite comprobar la versión legible | `manifest_checksum` SHA-256 y `synthetic` |
| `scene` | `scene_id` (UUID interno); `scene_identifier` conserva la identidad externa de Sentinel-2 | `lake_id`, `acquisition_date` y `synthetic` |
| `model` | `model_version_id` (UUID de versión objetivo) y `training_job_id` (referencia a la ejecución de entrenamiento en este manifiesto) | `algorithm`, `dataset_version_id` y `synthetic` |
| `execution` | `job_id` (UUID de `scientific_jobs`) | `organization_id`, `job_type`, `status`, `created_at` y `references` a las entidades anteriores |

`execution.references` repite las claves necesarias para encontrar las otras
tres entidades desde el trabajo. Son referencias declaradas por este formato
de evidencia; no se afirma que todas estén persistidas como columnas de una
fila de trabajo. El ejemplo se valida con:

```powershell
node docs/examples/validate_pilot_evidence_manifest.mjs
```

La comprobación valida la sintaxis JSON, los campos requeridos, UUID canónicos,
checksum, fecha y coherencia de las referencias. También analiza los bloques
`json` de los documentos indicados en el script. No comprueba que los UUID
existan en una base de datos ni que una inferencia haya ocurrido.

## Cómo localizar las entidades hoy

### Dataset y versión

- La persistencia define `dataset.datasets.id` y `dataset.versions.id`,
  `dataset.versions.dataset_id` y `dataset.versions.version_number`. Las
  versiones se enlazan al dataset mediante `dataset_id`.
- `GET /api/v1/datasets/review` devuelve datasets y versiones visibles para el
  usuario autenticado según su membership activa y rol. Para resolver un UUID
  concreto, recorre las páginas y compara `items[].id` y `versions[].id`.
- `GET /api/v1/datasets/{dataset_id}/versions/{version_id}/manifest` genera
  `dataset_id`, `version_id`, `version_number` y `manifest_checksum`. El
  checksum es calculado para la respuesta; no es una columna de
  `dataset.datasets` ni de `dataset.versions`. `dataset.training_manifests`
  guarda un checksum distinto, correspondiente al archivo de entrenamiento.
- **Brecha:** no hay endpoint dedicado de consulta por `dataset_id` ni por
  `dataset_version_id`. Además, el código del endpoint de manifiesto busca la
  versión por `version_id`, pero no comprueba que su `dataset_id` persistido
  coincida con el parámetro recibido; no debe usarse como sustituto de esa
  comprobación.

### Escena

- `GET /api/v1/lakes/{lake_id}/scenes?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  lista escenas del lago y rango solicitados. `items[].id` es el `scene_id`
  interno; `items[].scene_identifier` y `items[].acquisition_date` son claves
  de contraste. El endpoint no ofrece búsqueda directa por `scene_id`.
- La creación de tabla define `scenes.id` UUID, `lake_id`,
  `scene_identifier` y `acquisition_date`; la migración
  `015_create_satellite_scenes_table.sql` mueve `public.scenes` al esquema
  `satellite`. Sin embargo, los lectores de catálogo y Satellite consultan
  `client.table("scenes")` sin seleccionar explícitamente ese esquema.
- **Brecha de coherencia:** la ruta de listado existe en el código, pero la
  ubicación indicada por la migración y el esquema predeterminado usado por
  esos lectores no coinciden explícitamente. Hay que verificar la exposición
  de esquemas/configuración PostgREST del entorno antes de asumir que el
  endpoint encontrará filas tras aplicar todas las migraciones.

### Modelo

- `model_version_id` es el nombre de campo usado para una versión del modelo
  en los contratos científicos y en `public.scientific_jobs`; los contratos de
  estimación aceptan `model_id` como texto y admiten `model_version_id` UUID.
  `algorithm` puede describir el `model` del resultado de entrenamiento (por
  ejemplo, `baseline`).
- Para ubicar la ejecución de origen, usa `training_job_id` en
  `GET /api/v1/executions/{job_id}`. El endpoint
  `GET /api/v1/executions/{job_id}/artifact` solicita acceso al artefacto
  asociado a ese trabajo; requiere autenticación y `X-Organization-ID`.
- **Brecha:** no existe tabla `models`/`model_versions` ni endpoint de consulta
  de modelo por `model_version_id`. `scientific_model_scopes.id` identifica un
  alcance científico, no un modelo. El UUID `model_version_id` no es, por sí
  solo, una garantía de que exista un registro de modelo consultable; el
  enlace inequívoco al artefacto disponible hoy es el trabajo que lo contiene.
  El `training_job_id` incluido en este formato es una referencia de evidencia,
  no una FK ni una relación persistida y garantizada entre un modelo y su
  entrenamiento. Debe copiarse del trabajo de origen solo si el sistema puede
  demostrar esa relación.

### Ejecución

- La tabla usada por el servicio es `public.scientific_jobs`; su `id` es UUID
  y sus campos de organización/estado/fechas incluyen `organization_id`,
  `status`, `created_at`, `started_at` y `completed_at` (además de
  `job_type`, `config` y `result`).
- `GET /api/v1/executions/{job_id}` consulta por UUID de trabajo y requiere
  usuario autenticado y cabecera `X-Organization-ID`. La organización forma
  parte del alcance de lectura.
- `X-Correlation-ID` sirve para correlacionar logs/solicitudes, pero no es el
  identificador persistido del trabajo ni una columna de trazabilidad
  histórica.
- **Brecha de esquema:** `019_create_scientific_jobs_table.sql` crea otra tabla,
  `scientific.jobs`, que sí incluye `dataset_version_id`; el código de ejecución
  consulta `public.scientific_jobs`, creada por la migración 022. Las
  migraciones de `public.scientific_jobs` añaden `organization_id`,
  `model_version_id` y `scene_id`, pero no declaran `dataset_version_id`,
  aunque el código de ejecución lee/escribe ese campo en algunos flujos. El
  `dataset_version_id` de `execution.references` en este ejemplo es, por
  tanto, una referencia del manifiesto y no una afirmación de que esa columna
  exista en la tabla consultada por el servicio.

## Relación con los contratos existentes

El [versionado de datasets](./dataset-versioning.md) explica el fixture y su
checksum; la [guía del recorrido piloto](./pilot-estimation-guide.md) describe
la consulta de escenas y trabajos; y la
[decisión de arquitectura y evidencia de trazabilidad](./arquitectura_sprint2.md)
documenta `traceability_evidence` y `pilot_report`. Este manifiesto reúne
identificadores de referencia, no sustituye esos contratos ni afirma que el
worker ya emita evidencia completa. En particular, el contrato de
`traceability_evidence` es opcional y el worker no genera hoy todos sus
identificadores.
