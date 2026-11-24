# Ejemplos de Consumo API para Cliente Móvil (AquaBloom Sur)

Esta guía muestra cómo consumir la **misma API REST** de AquaBloom Sur desde la
aplicación móvil (React Native). No existe una API paralela ni endpoints
exclusivos para móvil: el cliente usa el API Gateway y los contratos publicados
en `/openapi.json`.

- **Base URL de producción:** `https://api.aquabloomsur.cl`
- **Base URL local de desarrollo:** `localhost:8000` (HTTP solo en local; nunca
  enviar JWT reales sin TLS).
- **Contrato de referencia:** `/openapi.json` del gateway y los archivos de
  `contracts/openapi/`. Si un contrato auxiliar difiere de la implementación,
  manda `/openapi.json` (ver sección 6).

## 1. Autenticación y organización activa

El login se realiza directamente contra **Supabase Auth**. La API no recibe
usuario/contraseña: solo valida el JWT emitido por Supabase.

### 1.1 Encabezados

| Encabezado | Obligatorio | Uso |
| --- | --- | --- |
| `Authorization: Bearer <JWT>` | En rutas protegidas | Identifica al usuario. |
| `X-Organization-ID: <UUID>` | En `/api/v1/executions/*` | Organización activa del usuario. |
| `X-Idempotency-Key` | Opcional en creación de trabajos | Evita duplicados. |
| `Accept: application/json` | Recomendado | Formato de respuesta. |

### 1.2 Rutas públicas y protegidas

Según la implementación actual (`apps/api/app/domains/catalog/controller_catalog.py`):

- **Públicas (no requieren JWT):**
  - `GET /api/v1/lakes`
  - `GET /api/v1/lakes/{lake_id}`
  - `GET /api/v1/lakes/{lake_id}/stations`
  - `GET /api/v1/lakes/{lake_id}/scenes`
- **Requieren JWT:**
  - `GET /auth/me`
  - `GET /api/v1/organizations/`
  - `GET /api/v1/scenes`
  - `POST /api/v1/executions/jobs`
  - `GET /api/v1/executions/{job_id}`

> `GET /api/v1/lakes?status=inactive` es la excepción dentro del catálogo: si se
> consulta sin un JWT con permisos, responde `403`.

### 1.3 Perfil del usuario

```bash
curl -X GET "https://api.aquabloomsur.cl/auth/me" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/json"
```

**Respuesta 200 OK:**

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "email": "usuario@aquabloom.cl",
  "memberships": [
    {
      "id": "22222222-2222-4222-8222-222222222222",
      "role": "admin",
      "status": "active",
      "organization": {
        "id": "33333333-3333-4333-8333-333333333333",
        "name": "AquaBloom Sur",
        "status": "active"
      }
    }
  ]
}
```

### 1.4 Organizaciones del usuario

El móvil debe obtener el `id` de la organización activa para enviarlo como
`X-Organization-ID` en los trabajos científicos.

```bash
curl -X GET "https://api.aquabloomsur.cl/api/v1/organizations/" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/json"
```

**Respuesta 200 OK:**

```json
[
  {
    "id": "33333333-3333-4333-8333-333333333333",
    "name": "AquaBloom Sur",
    "role": "admin"
  }
]
```

## 2. Catálogo de lagos, estaciones y escenas

### 2.1 Listar lagos (público)

- **Ruta:** `GET /api/v1/lakes`
- **Autenticación:** no requiere JWT para lagos activos.
- **Parámetros de consulta:**
  - `text` (opcional, mínimo 3 caracteres): búsqueda por nombre.
  - `region` (opcional): filtro exacto por región.
  - `status` (opcional): filtro exacto por estado. Por defecto `active`.
  - `page` (opcional, por defecto `1`, mínimo `1`).
  - `limit` (opcional, por defecto `10`, entre `1` y `100`).

> El parámetro de entrada es `limit`; el campo de respuesta es `page_size`.
> No existe `surface_area_km2` en la respuesta.

```bash
curl -X GET "https://api.aquabloomsur.cl/api/v1/lakes?page=1&limit=10" \
     -H "Accept: application/json"
```

**Respuesta 200 OK:**

```json
{
  "items": [
    {
      "name": "Lago Villarrica",
      "region": "Araucanía",
      "description": "Lago de origen glaciar",
      "id": "44444444-4444-4444-8444-444444444444",
      "status": "active",
      "stations_count": 5
    }
  ],
  "page": 1,
  "page_size": 10,
  "total": 1
}
```

### 2.2 Detalle de un lago (público)

- **Ruta:** `GET /api/v1/lakes/{lake_id}`
- **Autenticación:** no requiere JWT.
- **Respuesta:** `LakeDetail`, incluye `geom` (GeoJSON `Polygon`) y fechas.

```bash
curl -X GET "https://api.aquabloomsur.cl/api/v1/lakes/44444444-4444-4444-8444-444444444444" \
     -H "Accept: application/json"
```

**Respuesta 200 OK:**

```json
{
  "name": "Lago Villarrica",
  "region": "Araucanía",
  "description": "Lago de origen glaciar",
  "id": "44444444-4444-4444-8444-444444444444",
  "status": "active",
  "stations_count": 5,
  "geom": {
    "type": "Polygon",
    "coordinates": [
      [
        [-72.10, -39.60],
        [-72.20, -39.60],
        [-72.20, -39.70],
        [-72.10, -39.70],
        [-72.10, -39.60]
      ]
    ]
  },
  "created_at": "2026-09-30T10:00:00Z",
  "updated_at": "2026-09-30T10:00:00Z"
}
```

### 2.3 Estaciones de un lago (público)

- **Ruta:** `GET /api/v1/lakes/{lake_id}/stations`
- **Autenticación:** no requiere JWT.
- **Parámetros:** `status_filter` (opcional, por ejemplo `active`).
- **Respuesta:** arreglo de `StationOut`. Las coordenadas están en
  `point.coordinates` como `[longitud, latitud]`.

```bash
curl -X GET "https://api.aquabloomsur.cl/api/v1/lakes/44444444-4444-4444-8444-444444444444/stations?status_filter=active" \
     -H "Accept: application/json"
```

**Respuesta 200 OK:**

```json
[
  {
    "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "lake_id": "44444444-4444-4444-8444-444444444444",
    "code": "EST-01",
    "name": "Estación Centro",
    "point": {
      "type": "Point",
      "coordinates": [-72.335, -39.642]
    },
    "description": "Estación de monitoreo",
    "status": "active",
    "created_at": "2026-09-30T10:00:00Z",
    "updated_at": "2026-09-30T10:00:00Z"
  }
]
```

### 2.4 Escenas registradas de un lago (público)

- **Ruta:** `GET /api/v1/lakes/{lake_id}/scenes`
- **Autenticación:** no requiere JWT.
- **Parámetros obligatorios:** `start_date` y `end_date` en formato
  `YYYY-MM-DD`.
- **Parámetros opcionales:** `page` (por defecto `1`) y `page_size` (por
  defecto `20`, máximo `100`).
- **Errores:** `422` si `start_date > end_date`; `404` si el lago no existe.

```bash
curl -X GET "https://api.aquabloomsur.cl/api/v1/lakes/44444444-4444-4444-8444-444444444444/scenes?start_date=2026-03-01&end_date=2026-03-31&page=1&page_size=20" \
     -H "Accept: application/json"
```

**Respuesta 200 OK:**

```json
{
  "items": [
    {
      "id": "66666666-6666-4666-8666-666666666666",
      "lake_id": "44444444-4444-4444-8444-444444444444",
      "scene_identifier": "S2B_MSIL2A_20260315T143000_N0509_R053_T18HYC_20260315T164500",
      "acquisition_date": "2026-03-15",
      "created_at": "2026-03-16T08:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### 2.5 Variante autenticada de escenas

- **Ruta:** `GET /api/v1/scenes`
- **Autenticación:** requiere `Authorization: Bearer <JWT>`.
- **Parámetros obligatorios:** `lake_id`, `start_date`, `end_date`.
- **Parámetros opcionales:** `page` (por defecto `1`) y `page_size` (por
  defecto `10`, máximo `100`).
- **Respuesta:** mismo `PaginatedScenes` de la sección 2.4.

```bash
curl -X GET "https://api.aquabloomsur.cl/api/v1/scenes?lake_id=44444444-4444-4444-8444-444444444444&start_date=2026-03-01&end_date=2026-03-31&page=1&page_size=10" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/json"
```

> El contrato auxiliar `contracts/openapi/satellite.yaml` describe campos
> `external_id`, `provider` y `status` para `/scenes`, pero la implementación
> vigente responde `scene_identifier`, `acquisition_date` y `created_at`
> (`SceneOut`). Usar la implementación.

## 3. Trabajos científicos (entrenamiento y estimación)

### 3.1 Crear un trabajo

- **Ruta pública del gateway:** `POST /api/v1/executions/jobs`
- **Autenticación:** `Authorization: Bearer <JWT>`.
- **Encabezado obligatorio:** `X-Organization-ID: <UUID>`.
- **Encabezado opcional:** `X-Idempotency-Key` (máximo 255 caracteres).
- **Respuesta:** `202 Accepted` con `JobResponse`.

> No usar `POST /api/v1/executions/` desde el móvil: esa ruta es interna y
> exige `X-Internal-Token`. El gateway expone `POST /api/v1/executions/jobs`
> para los clientes web y móvil.

**Estimación:**

```bash
curl -X POST "https://api.aquabloomsur.cl/api/v1/executions/jobs" \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-Organization-ID: 33333333-3333-4333-8333-333333333333" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -d '{
           "job_type": "estimation",
           "config": {
             "model_id": "55555555-5555-4555-8555-555555555555",
             "scene_id": "66666666-6666-4666-8666-666666666666"
           }
         }'
```

**Entrenamiento:**

```json
{
  "job_type": "training",
  "config": {
    "dataset_id": "77777777-7777-4777-8777-777777777777",
    "version_id": "88888888-8888-4888-8888-888888888888",
    "epochs": 50,
    "learning_rate": 0.01
  }
}
```

**Respuesta 202 Accepted:**

```json
{
  "job_id": "99999999-9999-4999-8999-999999999999",
  "status": "queued",
  "status_url": "/api/v1/executions/99999999-9999-4999-8999-999999999999",
  "message": "Trabajo encolado y en procesamiento."
}
```

En `POST /api/v1/executions/jobs` solo se aceptan `training` y `estimation`
(también `TRAINING` y `ESTIMATION` por compatibilidad). El tipo `modeling` no
está implementado en esta ruta, aunque el enum de `JobStatus.job_type` sí lo
incluya. Para `training`, la versión puede enviarse en `config.version_id` o en
el campo superior `dataset_version_id`.

### 3.2 Consultar el estado (polling)

- **Ruta:** `GET /api/v1/executions/{job_id}`
- **Autenticación:** `Authorization: Bearer <JWT>`.
- **Encabezado obligatorio:** `X-Organization-ID: <UUID>`.
- **Respuesta:** **un objeto** `JobStatus` (no un arreglo).
- **Enums reales:**
  - `job_type`: `training`, `modeling`, `estimation` (la creación por
    `/api/v1/executions/jobs` solo admite `training` y `estimation`).
  - `status`: `queued`, `running`, `completed`, `failed`.

```bash
curl -X GET "https://api.aquabloomsur.cl/api/v1/executions/99999999-9999-4999-8999-999999999999" \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-Organization-ID: 33333333-3333-4333-8333-333333333333" \
     -H "Accept: application/json"
```

**Polling recomendado:**

1. Guardar el `job_id` y `status_url` devueltos al crear el trabajo.
2. Consultar `status_url` cada 2–5 segundos (con backoff si hay errores de red).
3. Detenerse cuando `status` sea `completed` o `failed`.
4. Si se recibe `404`, el trabajo no existe o no pertenece a la organización
   indicada: no reintentar indefinidamente.
5. No existe un endpoint de notificaciones push en el gateway; el móvil debe
   usar polling o notificaciones locales.

**Estado `queued`:**

```json
{
  "job_id": "99999999-9999-4999-8999-999999999999",
  "job_type": "estimation",
  "status": "queued",
  "config": {
    "model_id": "55555555-5555-4555-8555-555555555555",
    "scene_id": "66666666-6666-4666-8666-666666666666"
  },
  "result": null,
  "dataset_version_id": null,
  "model_version_id": null,
  "requested_by": "11111111-1111-4111-8111-111111111111",
  "error_message": null,
  "created_at": "2026-10-29T14:30:00Z",
  "started_at": null,
  "completed_at": null,
  "updated_at": "2026-10-29T14:30:00Z"
}
```

**Estado `running`:**

```json
{
  "job_id": "99999999-9999-4999-8999-999999999999",
  "job_type": "estimation",
  "status": "running",
  "config": {
    "model_id": "55555555-5555-4555-8555-555555555555",
    "scene_id": "66666666-6666-4666-8666-666666666666"
  },
  "result": null,
  "dataset_version_id": null,
  "model_version_id": null,
  "requested_by": "11111111-1111-4111-8111-111111111111",
  "error_message": null,
  "created_at": "2026-10-29T14:30:00Z",
  "started_at": "2026-10-29T14:30:05Z",
  "completed_at": null,
  "updated_at": "2026-10-29T14:30:05Z"
}
```

**Estado `completed` (ejemplo de entrenamiento con resultado estructurado):**

```json
{
  "job_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "job_type": "training",
  "status": "completed",
  "config": {
    "dataset_id": "77777777-7777-4777-8777-777777777777",
    "version_id": "88888888-8888-4888-8888-888888888888",
    "epochs": 50,
    "learning_rate": 0.01
  },
  "result": {
    "model": "baseline",
    "baseline": {
      "strategy": "mean_clorofila_a",
      "target_variable": "clorofila_a",
      "prediction_value": 15.0,
      "train_sample_count": 2,
      "validation_sample_count": 1
    },
    "prediction_value": 15.0,
    "predictions": [15.0],
    "metrics": {
      "mae": 15.0,
      "rmse": 15.0
    },
    "version": "88888888-8888-4888-8888-888888888888",
    "dataset_version_id": "88888888-8888-4888-8888-888888888888",
    "model_version_id": null,
    "status": "completed",
    "warnings": [
      "Modelo baseline de referencia basado en la media de clorofila_a de entrenamiento; no incorpora variables espectrales ni espaciales."
    ]
  },
  "dataset_version_id": "88888888-8888-4888-8888-888888888888",
  "model_version_id": null,
  "requested_by": "11111111-1111-4111-8111-111111111111",
  "error_message": null,
  "created_at": "2026-10-29T14:30:00Z",
  "started_at": "2026-10-29T14:30:05Z",
  "completed_at": "2026-10-29T14:35:00Z",
  "updated_at": "2026-10-29T14:35:00Z"
}
```

**Estado `failed`:**

```json
{
  "job_id": "99999999-9999-4999-8999-999999999999",
  "job_type": "estimation",
  "status": "failed",
  "config": {
    "model_id": "55555555-5555-4555-8555-555555555555",
    "scene_id": "66666666-6666-4666-8666-666666666666"
  },
  "result": null,
  "dataset_version_id": null,
  "model_version_id": null,
  "requested_by": "11111111-1111-4111-8111-111111111111",
  "error_message": "Tiempo máximo de ejecución excedido (Timeout de 10.0s).",
  "created_at": "2026-10-29T14:30:00Z",
  "started_at": "2026-10-29T14:30:05Z",
  "completed_at": "2026-10-29T14:30:15Z",
  "updated_at": "2026-10-29T14:30:15Z"
}
```

> `JobStatus` **no** incluye los campos `message` ni `result_url`. El resultado
> final está en `result`; el error está en `error_message`.

### 3.3 Idempotencia

- Si se envía `X-Idempotency-Key`, la misma clave con el mismo `job_type` y
  `config` devuelve el mismo `job_id`.
- La misma clave con contenido distinto responde `409 Conflict`.
- Una clave vacía responde `422`.
- Sin `X-Idempotency-Key`, cada solicitud crea un trabajo nuevo.

### 3.4 Resultado de una estimación

El resultado de una estimación se entrega dentro de `JobStatus.result` cuando
`status` es `completed`. **No existe** la ruta
`GET /api/v1/estimations/products/{id}` en el gateway; no debe usarse.

> En la implementación actual, un trabajo `estimation` no ejecuta inferencia:
> al completarse, `result` contiene
> `{"message": "Tipo de trabajo 'estimation' no implementado aún."}`. No asumir
> un producto de estimación ni una predicción numérica.

El microservicio `scientific` sí expone un detalle de predicción persistida en
`GET /api/v1/predictions/{prediction_id}` (requiere `Authorization` y
`X-Organization-ID`), pero esa ruta no aparece en el `/openapi.json` del
gateway. Si el despliegue la publica a través del proxy
`/api/v1/scientific/*`, el equipo de backend debe confirmar el prefijo exacto.

> **RN-10 — Advertencia de no toxicidad:** la estimación de clorofila-a es un
> indicador de biomasa algal y **no confirma toxicidad** del agua. El cliente
> móvil debe mostrar esta advertencia junto a cualquier valor estimado y no
> presentarlo como una confirmación sanitaria.

## 4. Errores estándar

La API responde con el sobre `{ "error", "message", "details" }`. El campo
`details` es opcional (o una lista en errores de validación).

| Código | Cuándo ocurre | Ejemplo de cuerpo |
| --- | --- | --- |
| `401` | JWT ausente, inválido o expirado | Ver ejemplo 401 |
| `403` | Permisos insuficientes | Ver ejemplo 403 |
| `404` | Recurso o trabajo inexistente, o fuera de la organización | Ver ejemplo 404 |
| `422` | Parámetros o encabezados inválidos/faltantes | Ver ejemplo 422 |
| `500` | Error interno no controlado | `{"error":"InternalServerError","message":"..."}` |

**401 Unauthorized:**

```json
{
  "error": "Unauthorized",
  "message": "El token JWT ha expirado.",
  "details": {
    "code": "TOKEN_EXPIRED"
  }
}
```

**403 Forbidden:**

```json
{
  "error": "HTTP Error",
  "message": "No tienes permisos para consultar lagos inactivos."
}
```

**404 Not Found:**

```json
{
  "error": "Not Found",
  "message": "No se encontró el trabajo."
}
```

**422 Validation Error** (por ejemplo, falta `X-Organization-ID`):

```json
{
  "error": "Validation Error",
  "message": "Parámetros de entrada inválidos",
  "details": [
    {
      "type": "missing",
      "loc": ["header", "X-Organization-ID"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

> Algunas respuestas documentadas en el OpenAPI usan el ejemplo
> `{code, message, details, request_id}`. Esos son ejemplos ilustrativos de
> `COMMON_ERRORS`; la forma que devuelve el runtime es
> `{error, message, details}`.

## 5. Checklist para el cliente móvil

- [ ] Usar `https://` en producción para todas las llamadas con JWT.
- [ ] Enviar `Authorization: Bearer <JWT>` en rutas protegidas.
- [ ] Enviar `X-Organization-ID` en `POST /api/v1/executions/jobs` y
      `GET /api/v1/executions/{job_id}`.
- [ ] Usar `limit` al pedir lagos y leer `page_size` en la respuesta.
- [ ] Usar `start_date`/`end_date` obligatorios al consultar escenas.
- [ ] Hacer polling de `status_url` hasta `completed` o `failed`.
- [ ] Tratar `JobStatus` como objeto individual, no como arreglo.
- [ ] Manejar `401`, `403`, `404` y `422` con mensajes claros.
- [ ] Mostrar la advertencia RN-10: clorofila-a no equivale a toxicidad.

## 6. Notas de contrato y discrepancias conocidas

- `/openapi.json` del gateway es la fuente de verdad para rutas, encabezados y
  esquemas.
- `contracts/openapi/satellite.yaml` describe `/scenes` con `external_id`,
  `provider` y `status`; la implementación vigente devuelve `SceneOut`
  (`scene_identifier`, `acquisition_date`, `created_at`). Usar la
  implementación.
- `POST /api/v1/executions/` es una ruta interna (`X-Internal-Token`). El móvil
  debe usar `POST /api/v1/executions/jobs`.
- No existe `/api/v1/estimations/products/{id}`. El resultado de la estimación
  se consulta en `JobStatus.result`.
- El detalle de predicción del microservicio `scientific`
  (`GET /api/v1/predictions/{prediction_id}`) no está incluido en el
  `/openapi.json` del gateway; confirmar con backend antes de consumirlo.
- No hay endpoint de notificaciones push; usar polling o notificaciones
  locales.
