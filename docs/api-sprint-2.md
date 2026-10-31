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


* **Ejemplo de consumo (React):**

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

* **Payload de Envío:**
{
  "name": "Lago Panguipulli (Revisado)",
  "status": "inactive"
}

* **Ejemplo de consumo (React):**

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

## Creación asíncrona de trabajos científicos

* **Ruta:** `POST /api/v1/executions/`
* **Autenticación:** header `X-Internal-Token`.
* **Entrenamiento:** requiere `dataset_id` y `version_id`; la versión debe
  pertenecer al dataset y estar en estado `PUBLISHED`.
* **Respuesta:** `202 Accepted` con `job_id`, `status` y `status_url`. La
  solicitud registra el trabajo como `pending`; no ejecuta el entrenamiento
  dentro del endpoint.

```json
{
  "job_type": "training",
  "config": {
    "dataset_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "version_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    "epochs": 50,
    "learning_rate": 0.01
  }
}
```

Consulta el estado con `GET /api/v1/executions/{job_id}`, usando también el
header `X-Internal-Token`.


### 4. Deshabilitar un Lago

Ruta: DELETE /api/v1/lakes/{lake_id}

* **Permisos requeridos:** catalog:disable (mediante la dependencia require_catalog_disable_permission).
* **Descripción:**  Realiza una desactivación lógica en la base de datos cambiando el estado a inactivo, dejando un registro de auditoría.

* **Ejemplo de consumo (React):**

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

* **Estructura de Respuesta (GeoJSON Point embebido):**

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


* **Ejemplo de consumo (React):**

export const fetchLakeStations = async (session, lakeId, statusFilter = '') => {
  const url = statusFilter 
    ? `/api/v1/lakes/${lakeId}/stations?status_filter=${statusFilter}`
    : `/api/v1/lakes/${lakeId}/stations`;
  const response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${session.access_token}` }
  });
  return await response.json();
};


### 2. Crear una Estación

Ruta: POST /api/v1/lakes/{lake_id}/stations

* **Permisos requeridos:** catalog:create (mediante la dependencia require_catalog_create_permission).
* **Descripción:** Registra una nueva estación asociada a un lago. Ejecuta validación geoespacial en la API.

* **Payload de Envío:**

{
  "code": "EST-02",
  "name": "Estación Norte",
  "description": "Nueva estación de monitoreo",
  "coordinates": {
    "latitude": -39.640,
    "longitude": -72.330
  },
  "status": "active"
}


* **Ejemplo de consumo (React):**

export const createStation = async (session, lakeId, stationData) => {
  const response = await fetch(`/api/v1/lakes/${lakeId}/stations`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(stationData)
  });
  return await response.json();
};

### 3. Actualizar una Estación

Ruta: PATCH /api/v1/stations/{station_id}

* **Permisos requeridos:** catalog:update (mediante la dependencia require_catalog_update_permission).
* **Descripción:** Modificación parcial de la estación. Si se envían coordenadas, la API ejecuta una validación geoespacial con PostGIS para garantizar que el nuevo punto esté dentro del lago asociado.

* **Payload de Envío (Objeto de Coordenadas):**

{
  "name": "Estación Centro (Reubicada)",
  "description": "Mantenimiento preventivo completado",
  "coordinates": {
    "latitude": -39.642,
    "longitude": -72.335
  },
  "status": "active"
}

* **Ejemplo de consumo (React):**

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

## Revisión y decisión de inclusión de datasets

Las rutas de revisión requieren una sesión Supabase válida. Solo se listan los
datasets pertenecientes a organizaciones donde el usuario tiene una membership
activa y un rol reconocido. El registro de decisiones se restringe a
`admin`, `administrador` y `supervisor` de la organización propietaria.

### Listar datasets y escenas para revisión

* **Ruta:** `GET /api/v1/datasets/review`
* **Respuesta:** datasets visibles, versiones y escenas. Cada escena incluye
  su historial de decisiones ordenado desde la más reciente.

```json
[
  {
    "id": "dataset-uuid",
    "organization_id": "organization-uuid",
    "name": "Dataset piloto",
    "versions": [
      {
        "id": "version-uuid",
        "version_number": 1,
        "status": "draft",
        "memberships": [
          {
            "id": "membership-uuid",
            "scene_provider": "sentinel",
            "scene_external_id": "scene-001",
            "decisions": []
          }
        ]
      }
    ]
  }
]
```

### Registrar decisión de inclusión

* **Ruta:** `POST /api/v1/datasets/memberships/{membership_id}/decisions`
* **Permisos:** membership activa en la organización del dataset con rol
  `admin`, `administrador` o `supervisor`.
* **Payload:** `decision` debe ser `accepted` o `rejected`; `reason` es
  obligatorio, no puede quedar en blanco y admite hasta 2000 caracteres.

```json
{
  "decision": "accepted",
  "reason": "La escena tiene cobertura válida."
}
```

La respuesta `201` contiene la decisión guardada. Un usuario sin permiso recibe
`403` y la interfaz debe mantener visible el motivo del rechazo.
## Listado acotado de escenas registradas

### Listar escenas de un lago

* **Ruta:** GET `/api/v1/lakes/{lake_id}/scenes`
* **Descripción:** Lista escenas que ya están registradas para un lago, filtrando por un rango inclusivo de fechas de adquisición. No consulta Copernicus ni inicia una búsqueda remota.
* **Parámetros requeridos:** `start_date` y `end_date` en formato `YYYY-MM-DD`.
* **Parámetros opcionales:** `page` (por defecto `1`) y `page_size` (por defecto `20`, máximo `100`).
* **Validación:** La fecha inicial debe ser anterior o igual a la fecha final. Un identificador de lago inexistente responde `404`.

Ejemplo:

```text
GET /api/v1/lakes/11111111-1111-1111-1111-111111111111/scenes?start_date=2026-03-01&end_date=2026-03-31&page=1&page_size=20
```

La respuesta usa el formato paginado `items`, `page`, `page_size` y `total`. Cada escena incluye su identificador, lago, identificador de escena, fecha de adquisición y fecha de registro. Para crear la tabla de registros, aplica `database/migrations/013_create_scenes_table.sql`.
