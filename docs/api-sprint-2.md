# Documentación API - Sprint 2 (AquaBloom Sur)

Este documento detalla los endpoints REST implementados durante el Sprint 2 para la gestión del catálogo de lagos y sus estaciones asociadas, alineados con el contrato OpenAPI del backend en FastAPI.

# Autenticación y Autorización

La API implementa un sistema de confianza cero basado en Supabase Auth.

* **Header Requerido**: Authorization: Bearer <TOKEN>
* **Validación**: Se utiliza la dependencia verify_supabase_jwt para validar la sesión.

## Endpoints del Catálogo de Lagos

### 1. Listar Catálogo de Lagos

* **Ruta:** GET /api/v1/lakes
* **Permisos requeridos:** Sesión activa válida.
* **Descripción:** Recupera el catálogo con soporte para paginación y filtros combinados.
* **Ejemplo de consumo (React):**

export const fetchLakes = async (session, page = 1) => {
  const response = await fetch(`/api/v1/lakes?page=${page}&limit=10`, {
    headers: { 'Authorization': `Bearer ${session.access_token}` }
  });
  return await response.json();
};


### 2. Crear un Lago

Ruta: POST /api/v1/lakes

* **Permisos requeridos:** catalog:create (mediante la dependencia require_catalog_create_permission).
* **Descripción:** Registra un nuevo lago en el catálogo. La validación exige que la geometría proporcionada sea estrictamente un polígono GeoJSON válido.

Payload de Envío (GeoJSON):

{
  "name": "Lago Panguipulli",
  "region": "Región de Los Ríos",
  "description": "Lago de origen glaciar",
  "geom": {
    "type": "Polygon",
    "coordinates": [[[-72.1, -39.6], [-72.2, -39.6], [-72.2, -39.7], [-72.1, -39.7], [-72.1, -39.6]]]
  }
}


# Ejemplo de consumo (React):

export const createLake = async (session, lakeData) => {
  const response = await fetch('/api/v1/lakes', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(lakeData)
  });
  return await response.json();
};


### 3. Actualizar un Lago

Ruta: PATCH /api/v1/lakes/{lake_id}

* **Permisos requeridos:** catalog:update (mediante la dependencia require_catalog_update_permission).
* **Descripción:** Actualización parcial. La validación bloquea intentos de vaciar el nombre del lago o enviar coordenadas vacías.

# Ejemplo de consumo (React):

export const updateLake = async (session, lakeId, updateData) => {
  const response = await fetch(`/api/v1/lakes/${lakeId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updateData)
  });
  return await response.json();
};


### 4. Deshabilitar un Lago

Ruta: DELETE /api/v1/lakes/{lake_id}

* **Permisos requeridos:** catalog:disable (mediante la dependencia require_catalog_disable_permission).
* **Descripción:**  Realiza una desactivación lógica en la base de datos cambiando el estado a inactivo, dejando un registro de auditoría.

# Ejemplo de consumo (React):

export const disableLake = async (session, lakeId) => {
  const response = await fetch(`/api/v1/lakes/${lakeId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${session.access_token}` }
  });
  return await response.json();
};


## Endpoints de Estaciones

### 1. Listar Estaciones por Lago

Ruta: GET /api/v1/lakes/{lake_id}/stations

* **Permisos requeridos:** Sesión activa válida.
* **Descripción:** Recupera todas las estaciones asociadas a un lago específico, permitiendo filtrado opcional.

Estructura de Respuesta (GeoJSON Point embebido):

[
  {
    "id": "uuid-v4",
    "lake_id": "uuid-v4",
    "code": "EST-01",
    "name": "Estación Centro",
    "point": {
      "type": "Point",
      "coordinates": [-72.335, -39.642]
    },
    "status": "active",
    "created_at": "2026-09-30T10:00:00Z",
    "updated_at": "2026-09-30T10:00:00Z"
  }
]


# Ejemplo de consumo (React):

export const fetchLakeStations = async (session, lakeId, statusFilter = '') => {
  const url = statusFilter 
    ? `/api/v1/lakes/${lakeId}/stations?status_filter=${statusFilter}`
    : `/api/v1/lakes/${lakeId}/stations`;
  const response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${session.access_token}` }
  });
  return await response.json();
};


### 2. Actualizar una Estación

Ruta: PATCH /api/v1/stations/{station_id}

* **Permisos requeridos:** catalog:update (mediante la dependencia require_catalog_update_permission).
* **Descripción:** Modificación parcial de la estación. Si se envían coordenadas, la API ejecuta una validación geoespacial con PostGIS para garantizar que el nuevo punto esté dentro del lago asociado.

Payload de Envío (Objeto de Coordenadas):

{
  "name": "Estación Centro (Reubicada)",
  "description": "Mantenimiento preventivo completado",
  "coordinates": {
    "latitude": -39.642,
    "longitude": -72.335
  },
  "status": "active"
}


# Ejemplo de consumo (React):

export const updateStation = async (session, stationId, updateData) => {
  const response = await fetch(`/api/v1/stations/${stationId}`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updateData)
  });
  return await response.json();
};
