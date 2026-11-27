# Ejemplos de errores para clientes Web y Móvil

Guía de referencia para los clientes web (React + TypeScript) y móvil
(React Native) de AquaBloom Sur. Cubre los cuatro escenarios exigidos por
S3-16 / AQU-370:

- sesión ausente o inválida (`401`);
- permiso insuficiente (`403`);
- dato inválido (`422`);
- dependencia caída (`503`).

Los ejemplos fueron contrastados con la implementación real del Gateway, la API
y los microservicios `satellite` y `scientific`. La fuente de verdad para rutas
y esquemas es el `/openapi.json` del Gateway.

## 1. Reglas comunes

- **TLS (RNF-01):** en producción usar siempre `https://`. `http://` solo se
  admite para desarrollo local (`http://localhost:8000`). No enviar JWT reales
  por HTTP.
- **Correlación (RNF-25):** toda respuesta incluye `X-Correlation-ID` (el valor
  recibido o un UUID generado). CORS expone esa cabecera al cliente web. El
  cuerpo de error real **no** incluye `request_id`; usar la cabecera para
  trazabilidad y soporte.
- **Compatibilidad (RF-75, RF-76):** ambos clientes deben interpretar el mismo
  código HTTP, mostrar el mismo mensaje de negocio y aceptar tanto el sobre
  `{error, message, details}` como el sobre heredado `{detail}` de algunos
  microservicios.
- **Sin reintentos ciegos:** `401`, `403` y `422` no se reintentan. Un `503` sí
  puede reintentarse con backoff y, en `POST`, con `X-Idempotency-Key`.

## 2. Sobres de error reales

La implementación vigente usa las siguientes formas. Un cliente robusto debe
revisar primero el código HTTP y luego leer `message` o `detail`.

| Origen | HTTP | Sobre real | Cuándo ocurre |
| --- | --- | --- | --- |
| `AuthException` (API) | `401` | `{"error":"Unauthorized","message":"...","details":{"code":"..."}}` | JWT inválido o expirado en rutas que usan `verify_supabase_jwt`. |
| `HTTPException` (API y `scientific`) | `401`, `403`, `404`, `422`, `503` | `{"error":"HTTP Error","message":"..."}` o `{"error":"Not Found","message":"..."}` | Permisos, recursos, reglas de negocio y dependencias no disponibles. |
| `RequestValidationError` (API y `scientific`) | `422` | `{"error":"Validation Error","message":"...","details":[...]}` | Body, query o encabezados que no cumplen el esquema. |
| Proxy del Gateway (`httpx.TransportError`) | `503` | `{"error":"ServiceUnavailable","message":"La dependencia solicitada no está disponible.","details":null}` | Fallo de transporte/conexión del Gateway hacia un microservicio. Incluye `X-Correlation-ID`. |
| `satellite` (a través del Gateway) | `422`, `503` | `{"detail":"..."}` | Validación o dependencia caída en el servicio Satellite. El Gateway conserva el cuerpo y agrega `X-Correlation-ID`. |
| Excepción no controlada | `500` | `{"error":"InternalServerError","message":"..."}` | Fallo inesperado no modelado. |

> Nota de contrato: los ejemplos de `apps/api/app/core/responses.py`
> (`COMMON_ERRORS`) usan `{code, message, details, request_id}`. Son ejemplos
> ilustrativos del OpenAPI, no el sobre que devuelve el runtime. Los clientes
> deben aceptar `error` y, por compatibilidad, también `code`.

### Normalizador TypeScript compartido

El siguiente adaptador sirve tanto para web como para React Native y tolera los
sobres `{error, message}`, `{code, message}` y `{detail}`:

```ts
export type NormalizedApiError = {
  status: number;
  code: string;
  message: string;
  details?: unknown;
  correlationId?: string;
};

export function normalizeApiError(
  status: number,
  body: unknown,
  correlationId?: string | null
): NormalizedApiError {
  const payload =
    body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
  const code =
    typeof payload.code === 'string'
      ? payload.code
      : typeof payload.error === 'string'
        ? payload.error
        : `HTTP_${status}`;
  const message =
    typeof payload.message === 'string'
      ? payload.message
      : typeof payload.detail === 'string'
        ? payload.detail
        : 'Error inesperado al consultar la API.';

  return {
    status,
    code,
    message,
    details: payload.details,
    correlationId: correlationId ?? undefined,
  };
}
```

## 3. Sesión ausente o inválida (`401`)

### 3.1 Sesión ausente

```bash
curl -i -X GET "https://api.aquabloomsur.cl/auth/me" \
     -H "Accept: application/json"
```

**Respuesta `401 Unauthorized`:**

```json
{
  "error": "HTTP Error",
  "message": "Not authenticated"
}
```

Cabeceras relevantes:

```text
X-Correlation-ID: 3f1c2a9e-6d6a-4f4e-9a0e-2b7c8d9e0f11
Content-Type: application/json
```

### 3.2 Token inválido o expirado

```bash
curl -i -X GET "https://api.aquabloomsur.cl/auth/me" \
     -H "Authorization: Bearer $TOKEN_INVALIDO" \
     -H "Accept: application/json"
```

**Token alterado o inválido (`401`):**

```json
{
  "error": "Unauthorized",
  "message": "Token JWT alterado o inválido.",
  "details": {
    "code": "INVALID_TOKEN"
  }
}
```

**Token expirado (`401`):**

```json
{
  "error": "Unauthorized",
  "message": "El token JWT ha expirado.",
  "details": {
    "code": "TOKEN_EXPIRED"
  }
}
```

Códigos posibles en `details.code`: `TOKEN_EXPIRED`, `INVALID_TOKEN`,
`INVALID_AUDIENCE`, `INVALID_ISSUER`, `MISSING_SUB`.

> En rutas que envuelven la validación en `scientific` (por ejemplo
> `GET /api/v1/executions/{job_id}`), el mismo token inválido puede responder
> `{"error":"HTTP Error","message":"Token JWT alterado o inválido."}` sin
> `details`. Decidir por el código HTTP, no por la forma del cuerpo.

### 3.3 Manejo en web

```ts
async function loadProfile(): Promise<void> {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Accept: 'application/json' },
  });

  if (res.status === 401) {
    await supabase.auth.signOut();
    if (!window.location.pathname.includes('/login')) {
      window.location.replace('/login');
    }
    const body = await res.json().catch(() => null);
    throw normalizeApiError(
      res.status,
      body,
      res.headers.get('X-Correlation-ID')
    );
  }
}
```

El cliente existente `apps/web/src/services/apiClient.ts` ya redirige a `/login`
ante `401`. Mantener ese comportamiento y conservar `X-Correlation-ID` para
soporte.

### 3.4 Manejo en móvil

```ts
async function loadProfile(token: string): Promise<Profile | null> {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
  });

  if (res.status === 401) {
    await supabase.auth.signOut();
    Alert.alert(
      'Sesión requerida',
      'Tu sesión expiró o no es válida. Inicia sesión nuevamente.'
    );
    navigation.reset({ index: 0, routes: [{ name: 'Login' }] });
    return null;
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const error = normalizeApiError(
      res.status,
      body,
      res.headers.get('X-Correlation-ID')
    );
    Alert.alert('No se pudo cargar el perfil', error.message);
    return null;
  }

  return (await res.json()) as Profile;
}
```

## 4. Permiso insuficiente (`403`)

Ejemplo real: consultar lagos inactivos sin un JWT con `catalog:disable`.

```bash
curl -i -X GET "https://api.aquabloomsur.cl/api/v1/lakes?status=inactive" \
     -H "Accept: application/json"
```

**Respuesta `403 Forbidden`:**

```json
{
  "error": "HTTP Error",
  "message": "No tienes permisos para consultar lagos inactivos."
}
```

Otros mensajes `403` implementados:

```json
{
  "error": "HTTP Error",
  "message": "No tienes permisos para crear lagos."
}
```

```json
{
  "error": "HTTP Error",
  "message": "Permisos insuficientes"
}
```

### 4.1 Manejo en web

```ts
function handleForbidden(error: NormalizedApiError): void {
  if (error.status !== 403) {
    return;
  }
  setPermissionMessage(error.message);
  setActionVisible(false);
}
```

No reintentar ni forzar la acción. Ocultar o deshabilitar la operación y
mostrar el `message` devuelto por la API.

### 4.2 Manejo en móvil

```ts
if (error.status === 403) {
  Alert.alert('Permiso insuficiente', error.message);
  return;
}
```

Usar exactamente el mismo texto de negocio que la web para cumplir RF-75.

## 5. Dato inválido (`422`)

### 5.1 Error de validación de FastAPI

Ejemplo real: crear un trabajo sin `X-Organization-ID`.

```bash
curl -i -X POST "https://api.aquabloomsur.cl/api/v1/executions/jobs" \
     -H "Authorization: Bearer $TOKEN" \
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

**Respuesta `422 Unprocessable Entity`:**

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

Ejemplo de query inválida:

```bash
curl -i -X GET "https://api.aquabloomsur.cl/api/v1/lakes?page=letras" \
     -H "Accept: application/json"
```

```json
{
  "error": "Validation Error",
  "message": "Parámetros de entrada inválidos",
  "details": [
    {
      "type": "int_parsing",
      "loc": ["query", "page"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "letras"
    }
  ]
}
```

### 5.2 Regla de negocio expresada como `422`

Algunos errores de negocio usan `HTTPException` con `422`; en ese caso no hay
`details` y el sobre es `HTTP Error`.

```bash
curl -i -X POST "https://api.aquabloomsur.cl/api/v1/executions/jobs" \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-Organization-ID: 33333333-3333-4333-8333-333333333333" \
     -H "Content-Type: application/json" \
     -d '{"job_type": "estimation", "config": {}}'
```

```json
{
  "error": "HTTP Error",
  "message": "La estimación requiere model_id y scene_id en config."
}
```

### 5.3 Manejo en web

```ts
function mapValidationDetails(error: NormalizedApiError): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  if (!Array.isArray(error.details)) {
    return fieldErrors;
  }

  for (const item of error.details) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const location = Array.isArray((item as { loc?: unknown }).loc)
      ? (item as { loc: unknown[] }).loc
      : [];
    const field = String(location[location.length - 1] ?? 'form');
    const msg = String((item as { msg?: unknown }).msg ?? error.message);
    fieldErrors[field] = msg;
  }

  return fieldErrors;
}
```

Mostrar los errores junto a cada campo cuando exista `details`; si no existe,
mostrar `error.message` como error general del formulario.

### 5.4 Manejo en móvil

```ts
if (error.status === 422) {
  const fieldErrors = mapValidationDetails(error);
  const firstMessage = Object.values(fieldErrors)[0] ?? error.message;
  Alert.alert('Datos inválidos', firstMessage);
  return;
}
```

En formularios móviles, mantener el mismo mapeo de campos y mensajes que la
web.

## 6. Dependencia caída (`503`)

El `503` puede provenir de la API/Gateway, de `scientific` o de `satellite`.
El Gateway conserva o genera `X-Correlation-ID` en la cabecera de respuesta.

### 6.1 API o `scientific` con base de datos no disponible

```bash
curl -i -X GET "https://api.aquabloomsur.cl/auth/me" \
     -H "Authorization: Bearer $TOKEN" \
     -H "Accept: application/json"
```

**Respuesta `503 Service Unavailable`:**

```json
{
  "error": "HTTP Error",
  "message": "El servicio de base de datos no está disponible"
}
```

### 6.2 `satellite` con Redis no disponible

```bash
curl -i -X POST "https://api.aquabloomsur.cl/api/v1/satellite/tasks/measurement-summary" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -d '{"measurements": [1.0, 2.0, 3.0]}'
```

**Respuesta `503 Service Unavailable`:**

```json
{
  "detail": "No se pudo encolar la tarea científica en Redis."
}
```

Cabeceras relevantes (agregadas por el Gateway):

```text
X-Correlation-ID: 9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a
Content-Type: application/json
```

### 6.3 Proxy del Gateway ante microservicio caído (`httpx.TransportError`)

Cuando el Gateway no logra comunicarse con un microservicio aguas abajo por un
error de transporte/conexión (`httpx.TransportError`, S3-15), responde `503`
con el sobre `ServiceUnavailable`:

```bash
curl -i -X GET "https://api.aquabloomsur.cl/api/v1/executions/99999999-9999-4999-8999-999999999999" \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-Organization-ID: 33333333-3333-4333-8333-333333333333" \
     -H "Accept: application/json"
```

**Respuesta `503 Service Unavailable`:**

```json
{
  "error": "ServiceUnavailable",
  "message": "La dependencia solicitada no está disponible.",
  "details": null
}
```

Cabeceras relevantes:

```text
X-Correlation-ID: 4b2e1c0a-8f7d-4e6b-9a1c-3d5e7f9a0b2c
Content-Type: application/json
```

> El cliente debe leer `message` o `detail`. No asumir que todo `503` trae el
> mismo formato de cuerpo.

### 6.4 Manejo en web

```ts
async function fetchWithBackoff<T>(
  request: () => Promise<Response>,
  maxAttempts = 3
): Promise<T> {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const res = await request();
    if (res.ok) {
      return (await res.json()) as T;
    }

    const body = await res.json().catch(() => null);
    const apiError = normalizeApiError(
      res.status,
      body,
      res.headers.get('X-Correlation-ID')
    );

    if (res.status !== 503 || attempt === maxAttempts) {
      throw apiError;
    }

    await new Promise((resolve) =>
      setTimeout(resolve, 1000 * 2 ** (attempt - 1))
    );
  }
  throw new Error('Reintentos agotados');
}
```

Para `POST /api/v1/executions/jobs`, reutilizar la misma
`X-Idempotency-Key` en cada reintento para evitar trabajos duplicados.

### 6.5 Manejo en móvil

```ts
if (error.status === 503) {
  Alert.alert(
    'Servicio temporalmente no disponible',
    'La plataforma está experimentando problemas. Intenta nuevamente en unos segundos.'
  );
  return;
}
```

Aplicar el mismo mensaje, número de reintentos y backoff que la web.

## 7. Paridad Web / Móvil

| Escenario | HTTP | Mensaje de negocio esperado | Reintento |
| --- | --- | --- | --- |
| Sesión ausente | `401` | `Not authenticated` | No |
| Token inválido/expirado | `401` | `Token JWT alterado o inválido.` / `El token JWT ha expirado.` | No; cerrar sesión |
| Permiso insuficiente | `403` | `No tienes permisos para ...` | No |
| Dato inválido | `422` | `Parámetros de entrada inválidos` o mensaje de regla | No |
| Dependencia caída | `503` | `La dependencia solicitada no está disponible.` / `El servicio de base de datos no está disponible` / `No se pudo encolar ...` | Sí, con backoff e idempotencia |

Checklist para ambos clientes:

- [ ] Interpretar primero el código HTTP y después el cuerpo.
- [ ] Aceptar `message`, `detail` y `details` (objeto o lista).
- [ ] Leer y registrar `X-Correlation-ID` en errores y en soporte.
- [ ] Usar `https://` en producción para cualquier petición con JWT.
- [ ] Mostrar los mismos mensajes de negocio en web y móvil.
- [ ] No reintentar `401`, `403` ni `422`.
- [ ] Reintentar `503` con backoff y `X-Idempotency-Key` en `POST`.
- [ ] En `401`, cerrar la sesión y redirigir al login.

## 8. Reproducción local

Variables de ejemplo (sin secretos reales):

```bash
export API_URL="http://localhost:8000"
export TOKEN="<jwt-de-emision-local>"
export TOKEN_INVALIDO="token-invalido"
```

Levantar la API local:

```bash
PYTHONPATH=. uvicorn apps.api.app.main:app --port 8000
```

Comandos de verificación:

```bash
curl -i "$API_URL/auth/me"
curl -i "$API_URL/api/v1/lakes?status=inactive"
curl -i "$API_URL/api/v1/lakes?page=letras"
curl -i "$API_URL/api/v1/datasets/review" -H "Authorization: Bearer $TOKEN"
```

El `503` del proxy del Gateway ocurre ante fallos de conexión `httpx` con un
microservicio aguas abajo; el `503` de base de datos ocurre cuando el cliente
de Supabase no está disponible; el `503` de Satellite ocurre cuando Redis no
está disponible. En todos los casos, el servidor debe detenerse al finalizar la
prueba para liberar el puerto.

## 9. Discrepancias conocidas

- Los ejemplos OpenAPI de `COMMON_ERRORS` incluyen `code` y `request_id`; el
  runtime devuelve `error` y expone la correlación solo en la cabecera.
- `satellite` responde con `{"detail": "..."}` para `422` y `503`, mientras la
  API, el proxy del Gateway y `scientific` usan `{error, message, details}`.
  Los clientes deben normalizar ambos formatos.
- Algunos errores de negocio usan `422` con el sobre `HTTP Error` en lugar de
  `Validation Error`. Nuevamente, el código HTTP es el criterio principal.
