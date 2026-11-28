# Verificación de estados terminales tras reinicio en staging (S3-43)

## Alcance y honestidad

La prueba automatizada local en
[`test_executions.py`](../apps/scientific/tests/test_executions.py) conserva
trabajos `completed` y `failed` en SQLite en disco, descarta la primera instancia,
crea una aplicación nueva y consulta los mismos `job_id`. También verifica el
aislamiento entre organizaciones después del arranque limpio.

Esto valida el contrato local con almacenamiento persistente simulado. No
demuestra que staging esté correcto ni sustituye una corrida contra el entorno
real: la ejecución en staging sigue pendiente y debe coordinarse aparte.
No se inventan resultados, fechas ni ejecuciones completadas.

## Topología real

En `compose.yaml` existen dos procesos relevantes:

- el servicio Compose `gateway` (Gateway/API) monta el router de ejecuciones:
  `POST /api/v1/executions/jobs` crea trabajos y
  `GET /api/v1/executions/{job_id}` consulta el estado. Atiende en el contenedor
  `gateway`, publicado como puerto `5000` en la configuración base.
- el servicio Compose `scientific` también monta el router de ejecuciones y
  expone `GET /api/v1/executions/{job_id}` y su health directo en el puerto
  `8003`.

El puente Web se ejecuta dentro del proceso Gateway. `POST .../jobs` crea y
procesa el trabajo contra la base compartida mediante `BackgroundTasks`; no
reenvía ese POST a Scientific ni lo publica en Redis. Por ello, para comprobar
el recorrido usado por Web y Móvil, se deben usar las rutas a través del
Gateway (`$STAGING_API_URL`) antes y después de reiniciar.

Scientific se reinicia para comprobar el contenedor de servicio independiente;
Gateway se reinicia por separado para comprobar el arranque limpio del recorrido
Gateway real. Ambos health checks usan exactamente `GET /api/v1/health`, tanto
en el Gateway como en Scientific.

## Requisitos

- Autorización del equipo para reiniciar `gateway` y `scientific` en staging.
- Un JWT válido de un usuario con membresía activa en una organización autorizada.
- Acceso interno aprobado al Gateway y, si se usa diagnóstico directo, a
  Scientific. No publiques el puerto `8003` en Internet.
- Bash, `curl`, `jq` y Docker Compose.
- Nunca envíes un JWT real por una URL remota `http://`. En staging remoto exige
  `https://` en `STAGING_API_URL` y en cualquier URL remota de Scientific.

Usa UUID sintéticos y una organización autorizada. No uses datos de producción
ni guardes respuestas de staging en el repositorio. Todos los archivos temporales
deben quedar fuera del checkout.

```bash
TMP_DIR="$(mktemp -d)"
trap 'unset STAGING_TOKEN; rm -rf "$TMP_DIR"' EXIT

export STAGING_API_URL="https://gateway.staging.aprobado.example"
export STAGING_SCIENTIFIC_URL="https://scientific.staging.aprobado.example"
export STAGING_ORG_ID="<UUID-de-organizacion-de-staging-autorizada>"

read -rsp "JWT de staging: " STAGING_TOKEN; echo
export STAGING_TOKEN

case "$STAGING_API_URL" in https://*) ;; *) echo "Se requiere https:// para staging remoto" >&2; exit 1;; esac
```

Si el entorno es local sobre Compose, sustituye las URL por las aprobadas:
`STAGING_API_URL=http://localhost:5000` y
`STAGING_SCIENTIFIC_URL=http://localhost:8003`. En un staging remoto nunca uses
`http://` para enviar el JWT.

## 1. Crear el trabajo `completed`

Encola el caso sintético a través del Gateway. Debe devolver HTTP `202 Accepted`
y el estado inicial `"queued"`.

```bash
HTTP_CODE="$(
  curl -sS -o "$TMP_DIR/completed-job.json" -w "%{http_code}" \
    -X POST "$STAGING_API_URL/api/v1/executions/jobs" \
    -H "Authorization: Bearer $STAGING_TOKEN" \
    -H "X-Organization-ID: $STAGING_ORG_ID" \
    -H "Content-Type: application/json" \
    -d '{
      "job_type": "ESTIMATION",
      "config": {
        "model_id": "11111111-2222-4333-8444-555555555555",
        "scene_id": "33333333-4444-4555-8666-777777777777"
      }
    }'
)"
test "$HTTP_CODE" = "202"
jq -e '.status == "queued"' "$TMP_DIR/completed-job.json"

export COMPLETED_JOB_ID="$(jq -r '.job_id' "$TMP_DIR/completed-job.json")"
test -n "$COMPLETED_JOB_ID" && test "$COMPLETED_JOB_ID" != "null"
```

## 2. Crear el trabajo `failed`

El identificador sintético no existe. También debe devolver HTTP `202 Accepted`
y el estado inicial `"queued"`.

```bash
HTTP_CODE="$(
  curl -sS -o "$TMP_DIR/failed-job.json" -w "%{http_code}" \
    -X POST "$STAGING_API_URL/api/v1/executions/jobs" \
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
    }'
)"
test "$HTTP_CODE" = "202"
jq -e '.status == "queued"' "$TMP_DIR/failed-job.json"

export FAILED_JOB_ID="$(jq -r '.job_id' "$TMP_DIR/failed-job.json")"
test -n "$FAILED_JOB_ID" && test "$FAILED_JOB_ID" != "null"
```

## 3. Confirmar estados terminales antes del reinicio

Consulta ambos trabajos por el Gateway, que representa el recorrido usado por
Web y Móvil. Repite hasta que sean terminales, sin reiniciar antes.

```bash
wait_terminal() {
  local job_id="$1"
  local expected="$2"
  local deadline=$((SECONDS + 120))
  local body

  while (( SECONDS < deadline)); do
    body="$TMP_DIR/poll-$job_id.json"
    if curl -fsS "$STAGING_API_URL/api/v1/executions/$job_id" \
      -H "Authorization: Bearer $STAGING_TOKEN" \
      -H "X-Organization-ID: $STAGING_ORG_ID" \
      -H "Accept: application/json" -o "$body"; then
      if jq -e --arg expected "$expected" '.status == $expected' "$body" >/dev/null; then
        cat "$body"
        return 0
      fi
    fi
    sleep 2
  done
  echo "Timeout esperando estado terminal para $job_id" >&2
  return 1
}

wait_terminal "$COMPLETED_JOB_ID" "completed" >"$TMP_DIR/before-completed.json"
wait_terminal "$FAILED_JOB_ID" "failed" >"$TMP_DIR/before-failed.json"

jq -e '.status == "completed" and .result != null and .error_message == null' \
  "$TMP_DIR/before-completed.json"
jq -e '.status == "failed" and .result == null and .error_message != null' \
  "$TMP_DIR/before-failed.json"
```

## 4. Reiniciar Gateway y Scientific

Ejecuta desde el host que administra los dos archivos Compose:

```bash
docker compose -f compose.yaml -f compose.staging.yaml ps gateway scientific

export GATEWAY_BEFORE="$(docker inspect -f '{{.Id}}|{{.State.StartedAt}}' \
  "$(docker compose -f compose.yaml -f compose.staging.yaml ps -q gateway)")"
export SCIENTIFIC_BEFORE="$(docker inspect -f '{{.Id}}|{{.State.StartedAt}}' \
  "$(docker compose -f compose.yaml -f compose.staging.yaml ps -q scientific)")"
printf 'Gateway before: %s\nScientific before: %s\n' \
  "$GATEWAY_BEFORE" "$SCIENTIFIC_BEFORE"

docker compose -f compose.yaml -f compose.staging.yaml restart gateway
docker compose -f compose.yaml -f compose.staging.yaml restart scientific

export GATEWAY_AFTER="$(docker inspect -f '{{.Id}}|{{.State.StartedAt}}' \
  "$(docker compose -f compose.yaml -f compose.staging.yaml ps -q gateway)")"
export SCIENTIFIC_AFTER="$(docker inspect -f '{{.Id}}|{{.State.StartedAt}}' \
  "$(docker compose -f compose.yaml -f compose.staging.yaml ps -q scientific)")"
printf 'Gateway after: %s\nScientific after: %s\n' \
  "$GATEWAY_AFTER" "$SCIENTIFIC_AFTER"
```

`docker compose ... restart` mantiene el mismo `Container ID`; reinicia el
proceso dentro del contenedor. `StartedAt` debe cambiar y/o el ID del proceso
se puede registrar con `docker inspect -f '{{.State.Pid}}'`. Si `StartedAt` no
cambia, no registres el reinicio como confirmado.

Espera hasta que Gateway y Scientific respondan saludables. Las dos rutas son
exactamente `/api/v1/health`:

```bash
wait_health() {
  local name="$1"
  local url="$2"
  local deadline=$((SECONDS + 120))

  while (( SECONDS < deadline)); do
    if curl -fsS "$url/api/v1/health" >/dev/null; then
      echo "$name healthy"
      return 0
    fi
    sleep 2
  done
  echo "$name unhealthy después del timeout" >&2
  return 1
}

wait_health gateway "$STAGING_API_URL"
wait_health scientific "$STAGING_SCIENTIFIC_URL"
```

Después de ambos health checks, consulta los mismos `job_id` únicamente a través
del Gateway:

```bash
curl -fsS "$STAGING_API_URL/api/v1/executions/$COMPLETED_JOB_ID" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Accept: application/json" >"$TMP_DIR/after-completed.json"

curl -fsS "$STAGING_API_URL/api/v1/executions/$FAILED_JOB_ID" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "X-Organization-ID: $STAGING_ORG_ID" \
  -H "Accept: application/json" >"$TMP_DIR/after-failed.json"
```

Compara estructuralmente antes y después sin acoplar la prueba a un mensaje
temporal de estimación:

```bash
jq '{status,result,error_message,requested_by,created_at,started_at,completed_at}' \
  "$TMP_DIR/before-completed.json" >"$TMP_DIR/completed-before-fields.json"
jq '{status,result,error_message,requested_by,created_at,started_at,completed_at}' \
  "$TMP_DIR/after-completed.json" >"$TMP_DIR/completed-after-fields.json"
diff -u "$TMP_DIR/completed-before-fields.json" "$TMP_DIR/completed-after-fields.json"

jq '{status,result,error_message,requested_by,created_at,started_at,completed_at}' \
  "$TMP_DIR/before-failed.json" >"$TMP_DIR/failed-before-fields.json"
jq '{status,result,error_message,requested_by,created_at,started_at,completed_at}' \
  "$TMP_DIR/after-failed.json" >"$TMP_DIR/failed-after-fields.json"
diff -u "$TMP_DIR/failed-before-fields.json" "$TMP_DIR/failed-after-fields.json"

jq -e --arg job "$COMPLETED_JOB_ID" '.job_id == $job and .status == "completed"' \
  "$TMP_DIR/after-completed.json"
jq -e --arg job "$FAILED_JOB_ID" '.job_id == $job and .status == "failed"' \
  "$TMP_DIR/after-failed.json"
```

Para verificar aislamiento multi-tenant después del reinicio, usa una segunda
organización a la que el usuario no pertenezca. La respuesta debe ser `404` y
no debe contener `error_message` ni el mensaje de error del trabajo `failed`:

```bash
export OTHER_ORGANIZATION_ID="<UUID-de-otra-organizacion-staging>"

for JOB_ID in "$COMPLETED_JOB_ID" "$FAILED_JOB_ID"; do
  HTTP_CODE="$(
    curl -sS -o "$TMP_DIR/forbidden-$JOB_ID.json" -w "%{http_code}" \
      "$STAGING_API_URL/api/v1/executions/$JOB_ID" \
      -H "Authorization: Bearer $STAGING_TOKEN" \
      -H "X-Organization-ID: $OTHER_ORGANIZATION_ID"
  )"
  test "$HTTP_CODE" = "404"
  ! jq -e 'has("error_message") or has("result") or has("job_id")' \
    "$TMP_DIR/forbidden-$JOB_ID.json" >/dev/null
done
```

La consulta SQL siguiente es opcional y solo debe ejecutarla una persona con
acceso de solo lectura a staging:

```sql
SELECT id, status, organization_id, requested_by, result, error_message,
       created_at, started_at, completed_at
FROM public.scientific_jobs
WHERE id IN ('<COMPLETED_JOB_ID>', '<FAILED_JOB_ID>');
```

No exportes resultados ni credenciales de base de datos a evidencias públicas.

## 5. Registrar evidencia

Registra únicamente evidencia saneada en el sistema aprobado para QA/staging.
No pegues JWT, claves, contraseñas ni datos de producción. Antes de pegarla en
el PR/ticket, sanitiza toda salida y elimina información sensible.

Todos los JSON se encuentran bajo `$TMP_DIR` fuera del repositorio y se eliminan
al salir de esta sesión por el `trap` configurado al inicio.

```text
Ticket: S3-43 / AQU-385
Entorno: staging (URL sin credenciales)
Fecha/hora UTC:
APP_VERSION / imagen:
Gateway service: gateway
Scientific service: scientific
Gateway Container ID antes / después:
Gateway StartedAt antes / después:
Scientific Container ID antes / después:
Scientific StartedAt antes / después:
Estado de salud Gateway después del reinicio: pendiente
Estado de salud Scientific después del reinicio: pendiente
Creación completed: HTTP 202 / status=queued confirmado (sí/no):
Creación failed: HTTP 202 / status=queued confirmado (sí/no):
Antes completed: HTTP 200 / status confirmado:
Después completed vía Gateway: HTTP 200 / diff estructural antes/después:
Antes failed: HTTP 200 / status confirmado:
Después failed vía Gateway: HTTP 200 / diff estructural antes/después:
Aislamiento completed con otra organización: HTTP 404 / sin datos terminales:
Aislamiento failed con otra organización: HTTP 404 / sin error_message:
organization_id validado por header y filtro (sí/no):
organization_id de fila comprobado por SQL de solo lectura (sí/no/no aplica):
Incidencias o desviaciones:
Ejecutor/autorización del reinicio:
```

Al finalizar, elimina el directorio temporal y el token:

```bash
unset STAGING_TOKEN
rm -rf "$TMP_DIR"
trap - EXIT
```
