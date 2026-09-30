# Documentación API - Sprint 2 (AquaBloom Sur)

Este documento detalla los endpoints REST implementados durante el Sprint 2 para la gestión del catálogo de lagos y sus estaciones asociadas, alineados con el contrato OpenAPI del backend en FastAPI.

## Autenticación y Autorización
La API implementa un sistema de confianza cero basado en Supabase Auth. 
* **Header Requerido:** `Authorization: Bearer <TOKEN>`
* **Validación:** Se utiliza la dependencia `verify_supabase_jwt` para validar la sesión.
* **Permisos Granulares:** Las acciones de mutación están protegidas por verificadores de permisos específicos como `require_catalog_create_permission`, `require_catalog_update_permission` y `require_catalog_disable_permission`.

---

## Endpoints del Catálogo de Lagos
Todas las rutas de este módulo utilizan el prefijo `/api/v1/lakes`.

### 1. Listar Catálogo de Lagos
* **Ruta:** `GET /api/v1/lakes`
* **Descripción:** Recupera el catálogo con soporte para paginación y filtros combinados.
* **Parámetros de Query:** `text` (min 3 caracteres), `region`, `status`, `page` (default: 1), `limit` (max 100).
* **Ejemplo de consumo (React):**
```typescript
const fetchLakes = async (session, page = 1) => {
  const response = await fetch(`/api/v1/lakes?page=${page}&limit=10`, {
    headers: { 'Authorization': `Bearer ${session.access_token}` }
  });
  return await response.json();
};
