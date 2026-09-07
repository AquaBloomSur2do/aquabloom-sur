# AquaBloom Sur

Plataforma científica colaborativa para la estimación de clorofila-a en lagos del sur de Chile mediante teledetección (Sentinel-2) y modelos de aprendizaje automático.

## Estructura del Monorepo

* **`apps/web/`**: Aplicación frontend web desarrollada en React con TypeScript y Vite. Contiene la interfaz de usuario, los flujos de revisión y la visualización cartográfica mediante MapLibre.
* **`apps/api/`**: Backend REST desarrollado en FastAPI (Python). Concentra las reglas de negocio, la validación de permisos y los controladores de la plataforma.
* **`database/migrations/`**: Scripts de migración SQL para el control de versiones del esquema de base de datos en PostgreSQL, incluyendo la configuración espacial con PostGIS.
* **`docs/`**: Documentación técnica del proyecto, contratos OpenAPI, diagramas de arquitectura de software y manuales de despliegue.

## Desarrollo Local

*(La documentación de requisitos, variables de entorno, Docker, semillas y pruebas se completará durante el cierre del Sprint 1).*