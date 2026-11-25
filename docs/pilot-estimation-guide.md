# Guía del recorrido piloto de estimación

Esta guía muestra cómo localizar una escena, solicitar un trabajo de
estimación y consultar su estado y, si ya existe una predicción persistida, su
detalle. Los ejemplos usan el Gateway local en `http://localhost:5000`.

## Prerrequisitos

- Gateway/API, Scientific y Satellite levantados; las escenas se consultan en
  Core. En `compose.yaml` los nombres de servicios son `gateway`, `core`,
  `scientific` y `satellite` (no existe un servicio Compose llamado `api`).
- Un JWT válido de usuario y una organización activa a la que pertenezca.
- El UUID del lago, un UUID de versión del modelo y un rango de fechas con
  escenas registradas.
- `curl` y, para las pruebas, Python con las dependencias de desarrollo.

En Git Bash, define las variables sin escribir el JWT directamente en los
comandos que compartas:

```bash
export API_URL="http://localhost:5000"
export TOKEN="<jwt-del-usuario>"
export ORG_ID="<uuid-organizacion-activa>"
export LAKE_ID="<uuid-del-lago>"
```

## 1. Consultar una escena registrada

Lista las escenas de un lago para un rango de fechas. Este endpoint no requiere
JWT. Toma `items[].id` como `scene_id`; `scene_identifier` es el identificador
externo de la escena, no el UUID que recibe el trabajo.

```bash
curl -sS -G "$API_URL/api/v1/lakes/$LAKE_ID/scenes" \
  --data-urlencode "start_date=2026-03-01" \
  --data-urlencode "end_date=2026-03-31" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20" \
  -H "Accept: application/json"
```

Respuesta esperada (`200 OK`, ejemplo):

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

Si `items` está vacío, prueba otro rango de fechas o lago. Un `404` indica que
el lago no existe; un `422` puede indicar fechas inválidas.

## 2. Solicitar una estimación

Envía el UUID de la versión del modelo como `model_id` y el UUID
`items[].id` de la escena como `scene_id`:

```bash
curl -sS -i -X POST "$API_URL/api/v1/executions/jobs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "job_type": "estimation",
    "config": {
      "model_id": "<uuid-version-modelo>",
      "scene_id": "<uuid-de-items-id>"
    }
  }'
```

La respuesta esperada es `202 Accepted` con un `job_id`, estado inicial y ruta
de consulta:

```json
{
  "job_id": "99999999-9999-4999-8999-999999999999",
  "status": "queued",
  "status_url": "/api/v1/executions/99999999-9999-4999-8999-999999999999",
  "message": "Trabajo encolado y en procesamiento."
}
```

Guarda el `job_id` devuelto y asígnalo a `JOB_ID` en la terminal:

```bash
export JOB_ID="<job_id-devuelto>"
```

## 3. Consultar estado y detalle de predicción

Consulta el trabajo con el JWT y la misma organización. Repite la llamada cada
2–5 segundos hasta que `status` sea `completed` o `failed`:

```bash
curl -sS "$API_URL/api/v1/executions/$JOB_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Accept: application/json"
```

La respuesta es un objeto `JobStatus`. Si termina con `failed`, revisa
`error_message`. **Limitación actual:** el worker no implementa trabajos
`estimation`; con la configuración de arriba puede marcar el trabajo como
`completed`, pero `result` será:

```json
{
  "message": "Tipo de trabajo 'estimation' no implementado aún."
}
```

Por lo tanto, ese trabajo no genera valores estimados ni un `prediction_id`.
El endpoint de detalle requiere el UUID de una predicción que ya haya sido
persistida por otro flujo. No se obtiene del `job_id`.

Si ya tienes ese identificador, consulta el detalle por el proxy del Gateway:

```bash
export PREDICTION_ID="<uuid-de-prediccion-persistida>"

curl -sS "$API_URL/api/v1/scientific/api/v1/predictions/$PREDICTION_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Accept: application/json"
```

La respuesta incluye `points[].value` (valor estimado), además de
`warnings`, `usage_limits` y `provenance`. Ejemplo ilustrativo basado en los
datos de prueba; los valores no son una predicción real:

```json
{
  "variable": "chlorophyll_a",
  "unit": "ug/L",
  "status": "completed",
  "points": [
    {"point_id": "est-01", "value": 14.8, "quality": "VALID"},
    {"point_id": "est-02", "value": 18.2, "quality": "EXTRAPOLATED"}
  ],
  "warnings": [
    "Punto est-02 excede el rango observado del modelo."
  ],
  "usage_limits": [
    "Una o más estimaciones están fuera del rango observado por el modelo (extrapolación).",
    "No se dispone de incertidumbre calibrada; el resultado no debe interpretarse como un intervalo de confianza."
  ]
}
```

La estimación de clorofila-a es un indicador de biomasa algal; no confirma la
toxicidad del agua. Presenta las advertencias y límites junto con cualquier
valor. Para recibir un detalle, el usuario debe tener acceso activo a la
organización; de lo contrario, la consulta devuelve `403`.

## Comprobación local mínima

Desde la raíz del repositorio:

```bash
docker compose up -d gateway core scientific satellite
curl -i "$API_URL/api/v1/health"
python -m pytest \
  apps/scientific/tests/test_executions.py::test_create_execution_job_returns_202 \
  apps/scientific/tests/test_predictions.py::test_get_prediction_detail_returns_full_contract_with_verified_permissions \
  -q
```

Los tests comprueban por separado la aceptación del trabajo y el contrato del
detalle de predicción; usan datos de prueba y no prueban una inferencia real de
extremo a extremo. Para esa inferencia, el worker de `estimation` debe estar
implementado y el trabajo debe producir o asociar un `prediction_id`.
