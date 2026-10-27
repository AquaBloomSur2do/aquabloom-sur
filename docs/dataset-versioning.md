# Persistencia mínima de versiones de datasets

La migración `database/migrations/013_create_dataset_versioning_schema.sql`
define las tablas de versionado dentro del esquema PostgreSQL `dataset`, separado
de `public`.

## Modelo

- `dataset.datasets`: identidad y metadatos básicos del dataset.
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
y escritura queda limitado a `service_role` mediante grants y RLS; no se crean
políticas de acceso directo para `anon` ni `authenticated`.

La migración crea el esquema y las tablas, pero no agrega `dataset` a los
esquemas expuestos por la API REST de Supabase. Si un servicio necesita acceder
al esquema por PostgREST, debe añadirse explícitamente en la configuración de
esquemas expuestos y usar el cliente con el esquema `dataset`.
