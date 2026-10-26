# Contraste de agrupación con la base del Sprint 1

## Objetivo

Documentar el inventario actual de procesos, módulos y servicios del proyecto para contrastarlo con la base funcional del Sprint 1, sin asumir que cualquier migración o cambio adicional ya quedó aplicado.

## 1. Inventario actual de procesos y módulos

### 1.1 Frontend (`apps/web`)

La capa de experiencia de usuario está agrupada en una aplicación React + TypeScript con Vite.

- `src/pages`: pantallas principales del producto (`Dashboard`, `LakesList`, `LakeDetail`, `Catalog`, `OrganizationsList`, `Profile`, `Login`, etc.).
- `src/components`: componentes reutilizables para catálogo, mapas, filtros, paginación y estados de carga.
- `src/contexts`: gestión de autenticación y estado compartido.
- `src/services`: cliente HTTP hacia la API y acceso a servicios de Supabase.
- `src/types`: contratos TypeScript para entidades del negocio.
- `src/layouts`: layout público y privado.

Procesos principales del frontend:
- autenticación y sesión del usuario;
- consulta y visualización del catálogo de lagos;
- gestión de estaciones asociadas;
- panel de control y vistas de dashboard;
- flujo de organización y perfiles;
- navegación protegida por roles y permisos.

### 1.2 Backend (`apps/api`)

La API está implementada con FastAPI y se organiza por dominios funcionales y servicios transversales.

- `app/auth.py`: autenticación y validación de sesión.
- `app/organizations.py`: organizaciones y memberships.
- `app/lakes.py`: gestión del catálogo de lagos.
- `app/stations.py`: gestión de estaciones.
- `app/dashboard.py`: panel de resumen y consultas de negocio.
- `app/imports.py`: flujo de importación de datos.
- `app/permissions.py`: controles de acceso y permisos.
- `app/repositories.py`: acceso a repositorios o recursos de datos.
- `app/schemas.py` y `app/serializers.py`: modelos y serialización de respuestas.
- `app/config.py`, `app/database.py`, `app/dependencies.py`: configuración, conexión y dependencias reutilizables.
- `app/main.py`: arranque y rutas globales.

Procesos principales del backend:
- validación de JWT con Supabase;
- control de permisos por entidad y acción;
- manipulación del catálogo geoespacial de lagos;
- gestión de estaciones por lago;
- auditoría y eventos de sistema;
- endpoints para dashboard y importaciones.

### 1.3 Base de datos y migraciones (`database/migrations`)

La base de datos se mantiene mediante migraciones SQL, con evolución progresiva del esquema.

Migraciones relevantes:
- `000_create_roles_table.sql`
- `001_create_profiles_table.sql`
- `002_create_organizations_table.sql`
- `003_create_memberships_table.sql`
- `004_create_lakes_table.sql`
- `005_create_stations_table.sql`
- `006_add_btree_gist_indexes.sql`
- `007_add_organization_status.sql`
- `008_create_audit_events_table.sql`
- `009_organization_member_support.sql`
- `010_add_email_to_profiles.sql`
- `011_create_imports_table.sql`
- `012_allow_profiles_read_rls.sql`

Estos archivos muestran que la capa de datos tiene una evolución continua y no debe asumirse que el estado de la base corresponde sólo al Sprint 1.

### 1.4 Documentación y contratos

- `README.md`: guía de instalación, ejecución local y verificación del monorepo.
- `docs/api-sprint-2.md`: documentación del contrato API del Sprint 2.

Esto permite mantener a la vez la operación local y la trazabilidad funcional de los módulos que ya existen.

## 2. Contraste con la base del Sprint 1

La base del Sprint 1 funcionaba como referencia de una plataforma con autenticación, catálogo y estructura inicial de lagos/estaciones. La agrupación actual evidencia una evolución hacia un monorepo más maduro:

- se separa claramente el frontend y el backend en `apps/web` y `apps/api`;
- se refuerza la modularización funcional del backend por dominio;
- se incorpora una capa de permisos más explícita y una base de datos con migraciones y auditoría;
- se agregan procesos de importación y dashboards que no forman parte de la base mínima del Sprint 1;
- la documentación ya no se limita a la ejecución, sino que también describe el contrato de la API y los flujos funcionales del Sprint 2.

En otras palabras, el proyecto ya no se comporta como un conjunto de módulos aislados del Sprint 1, sino como una plataforma con descomposición funcional más clara, controles de acceso y evolución del esquema.

## 3. Migraciones y cambios que exceden el sprint

No se debe asumir que toda la evolución funcional ya quedó implementada o aplicada. Se registran como trabajo adicional o pendiente de validación los siguientes elementos:

- migraciones SQL de evolución del esquema que puede requerir aplicación manual en entorno de desarrollo;
- cambios de permisos y RLS que afectan a perfiles, organizaciones y usuarios;
- módulos de importación y auditoría que requieren revisión de negocio y validación de datos reales;
- configuraciones de entorno, Supabase y variables `VITE_*` / `SUPABASE_*` que deben completarse en cada entorno;
- flujos de dashboard o reportes que no forman parte de la base mínima del Sprint 1 y deben contrastarse con la intención de negocio antes de cerrarse como finalizados.

## 4. Conclusión

El inventario actual muestra que la agrupación del proyecto ha evolucionado respecto a la base del Sprint 1, pero la comparación debe hacerse con criterio: se identifican módulos existentes, se documentan los procesos activos y se registran las migraciones o cambios que quedan fuera del alcance del sprint actual para evitar suponer que ya fueron completados.

Este registro sirve como referencia de trazabilidad para la validación del Sprint 2 y para cualquier revisión posterior de integración o migración.
