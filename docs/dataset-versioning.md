# Persistencia mínima de versiones de datasets

Las migraciones `013_create_dataset_versioning_schema.sql` y
`014_enforce_dataset_organization_isolation.sql` definen el versionado dentro
del esquema PostgreSQL `dataset`, separado de `public`, y su aislamiento por
organización.

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
