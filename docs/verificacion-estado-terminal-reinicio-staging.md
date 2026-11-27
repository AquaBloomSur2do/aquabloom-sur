# Verificación de estados terminales tras reinicio en staging (S3-43)

## Alcance y honestidad

La prueba automatizada local en
[`test_executions.py`](../apps/scientific/tests/test_executions.py) conserva
trabajos `completed` y `failed` en un SQLite en disco, crea una nueva instancia
de aplicación y un nuevo cliente de almacenamiento, y consulta los mismos
`job_id`. Esto verifica el contrato local de consulta contra almacenamiento
persistente simulado; no verifica una instancia viva de staging.

La verificación en staging requiere que una persona autorizada reinicie el
contenedor real `scientific` y repita las consultas. No se ejecutó staging
durante la preparación de esta guía.

El endpoint de consulta es `GET /api/v1/executions/{job_id}`. El Gateway y el
servicio `scientific` montan este router; la consulta lee
`public.scientific_jobs` por `id` y `organization_id`, no una caché en memoria.
`JobStatus` devuelve `job_id`, estado, resultado o error, y marcas de tiempo,
pero no expone `organization_id` en el JSON. La organización se valida con el
header `X-Organization-ID` y se aplica como filtro de consulta.

## Requisitos

- Autorización del equipo para realizar la prueba y reiniciar `scientific` en
  staging. Coordina el reinicio con quienes estén usando el entorno.
- Un JWT de un usuario con membresía activa en una organización de staging.
- Acceso a los endpoints de staging del Gateway y de Scientific. El servicio
  Compose `scientific` usa el puerto `8003`; el Gateway publica `5000` en la
  configuración base. En despliegues con ingress, sustituye las URL por las
  URL internas aprobadas.
- `curl` y `jq` en la terminal de Bash.

Usa una organización de staging autorizada y únicamente los UUID sintéticos de
los payloads siguientes. No uses datos de producción, no incluyas tokens en
archivos/evidencias y no guardes respuestas sin sanitizar en el repositorio.
En un host que ejecute el Compose de staging:

```bash
export STAGING_API_URL="http://localhost:5000"
export STAGING_SCIENTIFIC_URL="http://localhost:8003"
export STAGING_ORG_ID="<UUID-de-organizacion-de-staging-autorizada>"
read -rsp "JWT de staging: " STAGING_TOKEN; echo
export STAGING_TOKEN
```

En un staging remoto, configura `STAGING_API_URL` y
`STAGING_SCIENTIFIC_URL` con las direcciones aprobadas. No publiques el puerto
8003 en Internet para ejecutar esta prueba; usa acceso de red interno o un
túnel aprobado.

## 1. Crear un trabajo `completed` sintético

La estimación sin puntos ni trabajo de entrenamiento de origen recorre el
camino de ejecución actual sin requerir un modelo, escena o dataset existente.
El resultado declara la limitación actual de estimación; no representa una
predicción científica.

```bash
curl -fsS -X POST "$STAGING_API_URL/api/v1/executions/jobs" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "ESTIMATION",
    "config": {
      "model_id": "11111111-2222-4333-8444-555555555555",
      "scene_id": "33333333-4444-4555-8666-777777777777"
    }
  }' | tee completed-job.json

export COMPLETED_JOB_ID="$(jq -r '.job_id' completed-job.json)"
test -n "$COMPLETED_JOB_ID" && test "$COMPLETED_JOB_ID" != "null"
```

## 2. Crear un trabajo `failed` sintético

El identificador sintético de entrenamiento no existe. La ejecución aceptada
termina en `failed` con un mensaje conocido; no crea ni modifica datos de
entrenamiento.

```bash
curl -fsS -X POST "$STAGING_API_URL/api/v1/executions/jobs" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "ESTIMATION",
    "config": {
      "model_id": "11111111-2222-4333-8444-555555555555",
      "scene_id": "33333333-4444-4555-8666-777777777777",
      "training_job_id": "bbbbbbbb-2222-4222-8222-222222222222"
    }
  }' | tee failed-job.json

export FAILED_JOB_ID="$(jq -r '.job_id' failed-job.json)"
test -n "$FAILED_JOB_ID" && test "$FAILED_JOB_ID" != "null"
```

## 3. Confirmar los estados terminales antes del reinicio

Consulta directamente Scientific para confirmar que ambos trabajos ya
terminaron antes de reiniciar. Si un trabajo sigue `queued` o `running`, repite
su consulta cada 2–5 segundos; no reinicies hasta que ambos estén en estado
terminal.

```bash
curl -fsS "$STAGING_SCIENTIFIC_URL/api/v1/executions/$COMPLETED_JOB_ID" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Accept: application/json" | tee before-completed.json

curl -fsS "$STAGING_SCIENTIFIC_URL/api/v1/executions/$FAILED_JOB_ID" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Accept: application/json" | tee before-failed.json

jq -e '.status == "completed" and .result != null and .error_message == null' \
  before-completed.json
jq -e '.status == "failed" and .result == null and .error_message != null' \
  before-failed.json
```

## 4. Reiniciar Scientific y consultar los mismos trabajos

Ejecuta el reinicio desde el host/entorno que administra el proyecto Compose de
staging. Los nombres `compose.yaml`, `compose.staging.yaml` y `scientific` son
los definidos en este repositorio:

```bash
docker compose -f compose.yaml -f compose.staging.yaml ps scientific
docker compose -f compose.yaml -f compose.staging.yaml restart scientific
docker compose -f compose.yaml -f compose.staging.yaml ps scientific
curl -fsS "$STAGING_SCIENTIFIC_URL/api/v1/health"
```

Cuando el contenedor esté saludable, consulta de nuevo los mismos `job_id` al
servicio `scientific` reiniciado:

```bash
curl -fsS "$STAGING_SCIENTIFIC_URL/api/v1/executions/$COMPLETED_JOB_ID" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Accept: application/json" | tee after-completed.json

curl -fsS "$STAGING_SCIENTIFIC_URL/api/v1/executions/$FAILED_JOB_ID" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Accept: application/json" | tee after-failed.json

jq -e --arg job "$COMPLETED_JOB_ID" \
  '.job_id == $job and .status == "completed" and
   .result == {"message":"Tipo de trabajo '\''estimation'\'' no implementado aún."} and
   .error_message == null and (has("organization_id") | not)' after-completed.json
jq -e --arg job "$FAILED_JOB_ID" \
  '.job_id == $job and .status == "failed" and .result == null and
   .error_message == "No se encontró el trabajo de entrenamiento de origen del modelo."' \
  after-failed.json
```

`organization_id` no es parte de `JobStatus`, por lo que su ausencia en el JSON
es esperada; el header de organización debe ser el mismo usado para crear cada
trabajo. Si el equipo necesita verificar también el valor almacenado, una
persona con acceso de solo lectura a la base de staging puede ejecutar, fuera
del repositorio, esta consulta con los IDs obtenidos:

```sql
SELECT id, status, organization_id, requested_by, result, error_message
FROM public.scientific_jobs
WHERE id IN ('<COMPLETED_JOB_ID>', '<FAILED_JOB_ID>');
```

Confirma que ambas filas retienen la organización autorizada, el resultado
`completed` o el `error_message` de `failed`. La consulta SQL es opcional; no
exportes resultados ni credenciales de base de datos a evidencias públicas.

## 5. Registrar evidencia

Registra la evidencia en el sistema aprobado para QA/staging, no en este
repositorio. Elimina `completed-job.json`, `failed-job.json` y las respuestas
si contienen datos no destinados a compartirse. No registres JWT, claves,
contraseñas ni datos de producción.

```text
Ticket: S3-43
Entorno: staging (sin URL con credenciales)
Fecha/hora UTC:
APP_VERSION / imagen de scientific:
Container ID de scientific antes / después:
Estado de salud después del reinicio:
Job completado: HTTP antes/después; mismo job_id confirmado (sí/no);
  status=completed (sí/no); result conservado (sí/no)
Job fallido: HTTP antes/después; mismo job_id confirmado (sí/no);
  status=failed (sí/no); error_message conservado (sí/no)
organization_id validado por header y filtro (sí/no):
organization_id de fila comprobado por SQL de solo lectura (sí/no/no aplica):
Incidencias o desviaciones:
Ejecutor/autorización del reinicio:
```

Al finalizar, elimina los tokens de la sesión:

```bash
unset STAGING_TOKEN
```
