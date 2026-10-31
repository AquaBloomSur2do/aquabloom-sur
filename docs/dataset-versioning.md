# Módulo Dataset Oficial - AquaBloom Sur

## 1. Separación de Ingesta (Tarea S2-129)
El módulo `Dataset` ha sido separado estructuralmente del módulo `Ingestion`. 
* **Ingesta (`imports.py`):** Su responsabilidad termina al validar y almacenar archivos como "candidatos".
* **Dataset (`datasets.py`):** Es el único componente autorizado para evaluar candidatos y decidir su pertenencia a una versión oficial.

## 2. Reglas de Negocio del Dataset
* **Pertenencia explícita:** Las importaciones no se convierten automáticamente en registros oficiales. Deben ser incorporadas mediante el endpoint `/candidates/validate` y `/versions/{version_id}/candidates`.
* **Inmutabilidad:** Una vez que una versión alcanza el estado `PUBLISHED`, es inmutable.
* **Aislamiento Organizacional:** Solo los usuarios con rol de aprobación (`admin`, `supervisor`) dentro de la organización propietaria pueden modificar el estado o registrar decisiones.

## 3. Integración en el API Gateway
El módulo Dataset reside dentro del servicio `Core` y sus rutas (`/api/v1/datasets`) son servidas directamente por la aplicación FastAPI principal, mientras que las solicitudes a dominios satelitales y científicos son derivadas mediante el proxy del Gateway interno.
