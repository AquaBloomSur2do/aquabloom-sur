# Persistencia mínima de versiones de datasets

Las migraciones `013_create_dataset_versioning_schema.sql` y
`014_enforce_dataset_organization_isolation.sql` definen el versionado dentro
del esquema PostgreSQL `dataset`, separado de `public`, y su aislamiento por
organización.
La migración `database/migrations/013_create_dataset_versioning_schema.sql`
define las tablas de versionado dentro del esquema PostgreSQL `dataset`, separado
de `public`.

## Modelo

- `dataset.datasets`: identidad y metadatos básicos del dataset.
- `dataset.datasets.organization_id`: organización propietaria del dataset.
- `dataset.versions`: versiones numeradas de cada dataset; la numeración es
  positiva y única dentro del dataset.
- `dataset.memberships`: escenas pertenecientes a una versión, referenciadas por
  proveedor e identificador externo para no acoplar la persistencia a una tabla
  de escenas que no existe en el esquema actual.
- `dataset.decisions`: historial de decisiones `accepted` o `rejected` sobre una
  pertenencia, con actor, fecha y motivo opcional.

Las relaciones de versión, pertenencia y decisión eliminan sus registros
dependientes al borrar el registro padre. Los identificadores de usuario son
opcionales y se establecen a `NULL` al eliminar una cuenta. El acceso de lectura
y escritura de servicio queda limitado a `service_role`. RLS permite a usuarios
autenticados con membership activa de su organización y rol `admin`,
`administrador`, `supervisor`, `investigador` o `auditor` leer los datasets.
Solo `admin`, `administrador` y `supervisor` pueden insertar decisiones; un
miembro sin rol reconocido no puede leer ni decidir. `anon` no tiene acceso al
esquema.

La restricción `datasets_organization_required` se agrega como `NOT VALID` para
mantener inaccesibles filas antiguas sin propietario y exigir `organization_id`
en registros nuevos o actualizados. Asigna una organización a cualquier dataset
existente antes de validar esa restricción.
y escritura queda limitado a `service_role` mediante grants y RLS; no se crean
políticas de acceso directo para `anon` ni `authenticated`.

La migración crea el esquema y las tablas, pero no agrega `dataset` a los
esquemas expuestos por la API REST de Supabase. Si un servicio necesita acceder
al esquema por PostgREST, debe añadirse explícitamente en la configuración de
esquemas expuestos y usar el cliente con el esquema `dataset`.

## Prueba de aislamiento

Ejecuta `database/tests/014_dataset_rls_isolation.sql` en una base Supabase de
desarrollo/staging con permisos de administrador, después de aplicar las
migraciones 013 y 014. El script crea usuarios y datos de prueba dentro de una
transacción y termina con `ROLLBACK`. Comprueba lectura desde otra organización,
lectura y aprobación con rol sin permiso, lectura de un investigador de la
organización propietaria y aprobación por un supervisor.

## Revisión desde la aplicación

La interfaz web de revisión consume `GET /api/v1/datasets/review` y
`POST /api/v1/datasets/memberships/{membership_id}/decisions`. La API comprueba
la membership activa del usuario y su rol antes de listar datos o registrar una
decisión. Para que el cliente Supabase del backend consulte `dataset`, ese
esquema debe estar habilitado en la configuración **Exposed schemas** de la API
de Supabase, además de tener aplicadas las migraciones 013 y 014.

## Archivos de Entrenamiento (Training Files) - S2-137

Para garantizar la integridad y seguridad (Zero Trust), los archivos de entrenamiento se generan automáticamente cuando una versión transiciona al estado `PUBLISHED`.

- **Formato:** CSV UTF-8.
- **Columnas Estándar:** `temperatura`, `clorofila_a`, `turbidez`, `ph` (obtenidas dinámicamente del manifiesto).
- **Límite de Tamaño:** 1 MiB máximo por archivo.
- **Seguridad e Integridad:**
  - Se almacena en Supabase Storage (Bucket privado `training_files`).
  - La BD exige un checksum estrictamente formateado (SHA-256 de 64 caracteres).
  - Para evitar la fuga de URLs firmadas, la descarga del archivo se sirve mediante un proxy en la API (`/versions/{version_id}/training-file/download`) que exige validar el JWT por cada petición HTTP.

### Metadatos Avanzados del Manifiesto (S2-143)

Cada manifiesto generado incluye propiedades estrictas de trazabilidad:

- `manifest_version`: Versión del esquema del manifiesto (ej. `1.0.0`).
- `sources`: Listado de orígenes o identificadores de sensores que alimentaron el dataset.
- `is_experimental`: Bandera booleana que advierte si el set de datos proviene de pruebas de laboratorio o entornos no productivos.
- `is_synthetic`: Bandera booleana que indica si los datos fueron generados de forma artificial o sintética.

## Fronteras de Dominio con Ingesta (Sprint 2 - S2-129)

El módulo `Dataset` ha sido separado estructuralmente del módulo `Ingestion`.

- **Ingesta (`imports.py`):** Su responsabilidad termina al validar y almacenar archivos como "candidatos".
- **Dataset (`datasets.py`):** Es el único componente autorizado para evaluar candidatos y decidir su pertenencia a una versión oficial.

### Reglas de Negocio del Dataset

- **Pertenencia explícita:** Las importaciones no se convierten automáticamente en registros oficiales. Deben ser incorporadas mediante el endpoint `/candidates/validate` y `/versions/{version_id}/candidates`.
- **Inmutabilidad:** Una vez que una versión alcanza el estado `PUBLISHED`, es inmutable.
- **Aislamiento Organizacional:** Solo los usuarios con rol de aprobación (`admin`, `supervisor`) dentro de la organización propietaria pueden modificar el estado o registrar decisiones.

### Integración en el API Gateway

El módulo Dataset reside dentro del servicio `Core` y sus rutas (`/api/v1/datasets`) son servidas directamente por la aplicación FastAPI principal, mientras que las solicitudes a dominios satelitales y científicos son derivadas mediante el proxy del Gateway interno.
