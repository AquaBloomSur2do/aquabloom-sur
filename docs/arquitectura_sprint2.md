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