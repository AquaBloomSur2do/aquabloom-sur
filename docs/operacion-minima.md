# Guía de operación mínima

Procedimientos verificados para desarrollo local y Docker Compose. Ejecuta los
comandos Compose desde la raíz del repositorio. Los ejemplos de terminal local
usan PowerShell; adapta la activación del entorno Python si usas otro sistema.

## Topología y salud

| Servicio | Puerto local | Puerto publicado por Compose | Endpoint de salud / comprobación |
| --- | ---: | ---: | --- |
| API Gateway (`gateway`) | `8000` | `5000` | `GET /api/v1/health` |
| Core API (`core`) | — | `8001` | `GET /api/v1/health` |
| Scientific | `8003` | `8003` | `GET /api/v1/health` |
| Satellite | `8002` | `8002` | `GET /health` (comprueba Redis) |
| Web | `5173` | `3000` | No tiene healthcheck definido |
| Redis | Depende de Redis local | Solo red interna; no publica puerto | `redis-cli ping` en Compose |
| `scientific-worker` | No aplica | No publica puerto | El healthcheck del contenedor solo hace `PING` a Redis; confirma que consume mirando sus logs |

Compose no define un contenedor Postgres: la API y Scientific requieren la
configuración de Supabase. El Gateway y Core comparten la imagen y la aplicación
de `apps/api`, iniciadas en puertos distintos.

## Variables de entorno

Las variables requeridas son las que no tienen valor predeterminado en el
`Settings` del servicio o que el cliente valida al arrancar. Usa valores de tu
entorno local; los ejemplos que parecen credenciales son placeholders y no son
credenciales funcionales.

### API (`apps/api/app/core/config.py`)

| Variable | Obligatoria | Propósito | Ejemplo seguro |
| --- | --- | --- | --- |
| `SUPABASE_URL` | Sí | URL del proyecto Supabase. | `https://<project-ref>.supabase.co` |
| `SUPABASE_KEY` | Sí | Clave de servidor para la API; mantener fuera del frontend. | `<SUPABASE_SERVICE_KEY>` |
| `ENVIRONMENT` | No; `development` | Entorno de ejecución. | `development` |
| `CORS_ORIGINS` | No; `http://localhost:5173` | Orígenes permitidos, separados por comas. | `http://localhost:5173` |
| `SATELLITE_SERVICE_URL` | No; `http://satellite:8000` | Destino del proxy del Gateway a Satellite. | `http://satellite:8002` en Compose |
| `SCIENTIFIC_SERVICE_URL` | No; `http://scientific:8000` | Destino del proxy del Gateway a Scientific. | `http://scientific:8003` en Compose |
| `INTERNAL_SERVICE_TOKEN` | No | Token para llamadas internas cuando se configure en los servicios. | `<INTERNAL_TOKEN>` |
| `SUPABASE_JWT_SECRET` | No | Secreto opcional de validación JWT. | `<JWT_SECRET>` |

En `compose.staging.yaml`, Gateway recibe los destinos `satellite:8002` y
`scientific:8003`. En el Compose base los defaults `*:8000` no corresponden a
los puertos actuales de esos contenedores; si necesitas proxy desde Gateway
usando solo `compose.yaml`, configura `SATELLITE_SERVICE_URL` y
`SCIENTIFIC_SERVICE_URL` en `apps/api/.env`.

### Scientific (`apps/scientific/app/core/config.py`)

| Variable | Obligatoria | Propósito | Ejemplo seguro |
| --- | --- | --- | --- |
| `SUPABASE_URL` | Sí | URL del proyecto Supabase. | `https://<project-ref>.supabase.co` |
| `SUPABASE_KEY` | Sí | Clave de servidor del servicio. | `<SUPABASE_SERVICE_KEY>` |
| `ENVIRONMENT` | No; `development` | Entorno de ejecución. | `staging` |
| `CORS_ORIGINS` | No; `http://localhost:5173` | Orígenes permitidos. | `http://localhost:5173` |
| `CORE_API_URL` | No; `http://localhost:8000` | URL base de Core usada al consumir datasets publicados. | `http://core:8001` en Compose |
| `JOB_TIMEOUT_SECONDS` | No; `10.0` | Tiempo máximo configurado para un trabajo científico. | `10.0` |
| `INTERNAL_SERVICE_TOKEN` | No | Token opcional para llamadas internas. | `<INTERNAL_TOKEN>` |
| `SUPABASE_JWT_SECRET` | No | Secreto opcional de validación JWT. | `<JWT_SECRET>` |

### Satellite (`apps/satellite/app/core/config.py`)

Las variables de configuración tienen el prefijo `SATELLITE_`.

| Variable | Obligatoria | Propósito | Ejemplo seguro |
| --- | --- | --- | --- |
| `SATELLITE_SERVICE_NAME` | No; `AquaBloom Satellite` | Nombre incluido en la respuesta de `/health`. | `aquabloom-satellite` |
| `SATELLITE_ENVIRONMENT` | No; `development` | Entorno informado por el servicio. | `staging` |
| `SATELLITE_REDIS_URL` | No; `redis://localhost:6379/0` | Conexión Redis para la cola `scientific:tasks`. | `redis://redis:6379/0` en Compose |
| `SATELLITE_PORT` | No; `8002` | Puerto consultado por el healthcheck de la imagen. | `8002` |

El comando Uvicorn de Compose fija el listener de Satellite en `8002`; no
cambies `SATELLITE_PORT` de forma aislada en Compose, porque también debe
coincidir con el puerto en escucha.

### Web (`apps/web`)

| Variable | Obligatoria | Propósito | Ejemplo seguro |
| --- | --- | --- | --- |
| `VITE_SUPABASE_URL` | Sí | URL del proyecto Supabase del cliente. | `https://<project-ref>.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | Sí | Clave publicable/anon de Supabase; nunca uses una clave de servicio aquí. | `<SUPABASE_ANON_KEY>` |
| `VITE_API_URL` | No; `http://localhost:5000/api/v1` | URL base de la API. | `http://localhost:8000/api/v1` para la API local |

### Worker y variables inyectadas por Compose

| Variable | Obligatoria | Propósito | Ejemplo seguro |
| --- | --- | --- | --- |
| `REDIS_URL` | No para el proceso; usa `redis://redis:6379/0` por defecto | Conexión Redis que lee `scientific-worker`. El override de staging también la entrega al servicio Scientific. | `redis://localhost:6379/0` para un Redis accesible desde el proceso local |
| `APP_VERSION` | No; `dev` en el worker | Versión incluida en logs; Compose staging usa `staging-local` si no se define. | `staging-local` |
| `SCIENTIFIC_PORT` | No; `8003` en la imagen | Puerto usado por el healthcheck de la imagen Scientific. El comando Uvicorn de Compose sigue usando `8003`. | `8003` |
| `SCIENTIFIC_SERVICE_NAME` | No | Está en `apps/scientific/.env.example`, pero no es un campo de Scientific `Settings` y se ignora en esa configuración. | `aquabloom-scientific` |

`compose.staging.yaml` también fija `ENVIRONMENT=staging` para Gateway, Core,
Scientific y el worker; `SATELLITE_ENVIRONMENT=staging` para Satellite;
`SATELLITE_REDIS_URL=redis://redis:6379/0` para Satellite; y
`CORE_API_URL=http://core:8001` para Scientific. El archivo pasa además
`CORE_API_URL` al Gateway/Core, aunque la configuración actual de la API no
tiene un campo que lo consuma. No confundas `REDIS_URL` (worker/Scientific)
con `SATELLITE_REDIS_URL` (Satellite).

## Arranque, detención y estado

### Ejecución local

Prepara archivos `.env` locales desde las plantillas existentes y reemplaza los
valores de Supabase con configuración válida, sin copiar credenciales a esta
guía.

API, desde una terminal:

```powershell
cd apps/api
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Scientific, desde la raíz en otra terminal:

```powershell
python -m pip install -r apps/scientific/requirements.txt
python -m uvicorn apps.scientific.app.main:app --host 127.0.0.1 --port 8003
```

Satellite, desde la raíz. Debe haber un Redis local accesible; el valor por
defecto de Satellite apunta a `localhost:6379`:

```powershell
python -m pip install -r apps/satellite/requirements.txt
python -m uvicorn apps.satellite.app.main:app --host 127.0.0.1 --port 8002
```

Para ejecutar el worker directamente desde la raíz, usa el mismo Redis local y
asegura que `REDIS_URL` apunte a él. El repositorio no define un comando para
instalar o iniciar Redis fuera de Compose:

```powershell
python -m pip install -r apps/scientific/requirements.txt
$env:REDIS_URL = "redis://localhost:6379/0"
python -m apps.scientific.app.worker
```

Web, desde `apps/web`:

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

Cada proceso local se detiene con `Ctrl+C`; para reiniciarlo, vuelve a ejecutar
su comando. Comprueba los servicios HTTP con:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8003/api/v1/health
Invoke-RestMethod http://localhost:8002/health
Invoke-WebRequest http://localhost:5173
python -c "from redis import Redis; print(Redis.from_url('redis://localhost:6379/0').ping())"
```

`/health` de Satellite devuelve `503` si no puede alcanzar Redis. La salud de la
API puede informar `status: degraded` cuando Supabase no está disponible, aunque
el endpoint responda HTTP `200`. Web devuelve HTML en la URL raíz y la
comprobación Python de Redis devuelve `True` si responde al `PING`.

### Docker Compose base

Desde la raíz, arranca o reconstruye todos los servicios definidos en
`compose.yaml`:

```powershell
docker compose up -d --build
docker compose ps
```

Este Compose incluye Redis, Gateway, Core, Satellite, Scientific y Web; no
incluye `scientific-worker`. Para detener todos los contenedores:

```powershell
docker compose stop
```

Para reiniciar un servicio sin reiniciar el resto:

```powershell
docker compose restart gateway
docker compose restart scientific
docker compose restart satellite
docker compose restart web
docker compose restart redis
```

Revisa el estado, endpoints y Redis:

```powershell
docker compose ps
Invoke-RestMethod http://localhost:5000/api/v1/health
Invoke-RestMethod http://localhost:8001/api/v1/health
Invoke-RestMethod http://localhost:8003/api/v1/health
Invoke-RestMethod http://localhost:8002/health
Invoke-WebRequest http://localhost:3000
docker compose exec redis redis-cli ping
```

Espera `PONG` de Redis y `status: ok` en Satellite cuando Redis está conectado.
El estado de salud de la API puede ser `degraded` si Supabase no responde.
Compose no define healthcheck para Web.

### Compose con worker (override de staging)

`scientific-worker` se define en `compose.staging.yaml`, por lo que todos los
comandos que lo incluyan deben cargar ambos archivos, en ese orden:

```powershell
docker compose -f compose.yaml -f compose.staging.yaml up -d --build
docker compose -f compose.yaml -f compose.staging.yaml ps
docker compose -f compose.yaml -f compose.staging.yaml logs -f scientific-worker
```

Para detener el conjunto o reiniciar solo el worker:

```powershell
docker compose -f compose.yaml -f compose.staging.yaml stop
docker compose -f compose.yaml -f compose.staging.yaml restart scientific-worker
```

El worker comparte la red de Compose y depende de que Redis esté saludable. Su
healthcheck ejecuta `PING`; consulta los logs para comprobar que inició el bucle
de consumo y está escuchando la cola.

## Consulta de fallos y correlación

Consulta logs recientes y sigue el servicio que presenta el problema:

```powershell
docker compose logs --tail=100 gateway
docker compose logs --tail=100 core
docker compose logs --tail=100 satellite
docker compose logs --tail=100 scientific
docker compose logs --tail=100 web
docker compose logs --tail=100 redis
docker compose -f compose.yaml -f compose.staging.yaml logs --tail=100 scientific-worker
```

Para revisar un incidente en vivo, añade `-f` al comando de logs. El worker
informa conexión a Redis, tareas completadas, errores de Redis y tareas
descartadas por formato inválido.

Gateway, Scientific y Satellite aceptan `X-Correlation-ID` y lo devuelven en la
respuesta. Gateway conserva un valor válido o genera un UUID y lo propaga al
servicio llamado a través de sus rutas `/api/v1/satellite/*` y
`/api/v1/scientific/*`. Satellite copia el ID en el mensaje de la cola
`scientific:tasks`; el worker lo registra junto al `task_id`. Por ejemplo, en
Compose staging, envía una tarea pasando un ID reconocible:

```powershell
$correlationId = "ops-S2-190-001"
Invoke-RestMethod `
  -Uri http://localhost:5000/api/v1/satellite/tasks/measurement-summary `
  -Method Post `
  -Headers @{ "X-Correlation-ID" = $correlationId } `
  -ContentType "application/json" `
  -Body '{"measurements":[1.2,2.4,3.6]}'
```

La respuesta contiene `task_id` y `status: queued`. Busca el identificador en
los logs de Gateway, Satellite y worker:

```powershell
docker compose -f compose.yaml -f compose.staging.yaml logs --since=15m gateway satellite scientific-worker |
  Select-String -Pattern $correlationId
```

Scientific HTTP solo aparecerá en ese seguimiento si la solicitud también se
reenvía a Scientific; la cola de `measurement-summary` no pasa por ese servicio.
Además, `/api/v1/executions/jobs` es un flujo separado: usa `BackgroundTasks`
dentro del proceso Gateway y no usa `scientific-worker` ni Redis. En local, el
Gateway usa por defecto destinos `satellite:8000` y `scientific:8000`; ajusta
`SATELLITE_SERVICE_URL` y `SCIENTIFIC_SERVICE_URL` a puertos locales `8002` y
`8003` si pruebas el proxy.

Fallos habituales:

- **API o Scientific no inicia:** comprueba `SUPABASE_URL` y `SUPABASE_KEY`;
  ambos son requeridos por su configuración. No reemplaces los placeholders
  con credenciales en archivos versionados.
- **Gateway responde `503` al usar el proxy:** comprueba los logs del Gateway y
  que `SATELLITE_SERVICE_URL`/`SCIENTIFIC_SERVICE_URL` apunten al puerto donde
  escucha el servicio destino.
- **Satellite `/health` responde `503` o no acepta tareas:** comprueba el
  estado de Redis, `SATELLITE_REDIS_URL` y los logs de Satellite.
- **Worker no inicia o no procesa:** verifica `REDIS_URL`, que Redis esté
  saludable y que el worker esté ejecutándose y registrando que escucha
  `scientific:tasks`.
- **Web no inicia:** define `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`;
  `VITE_API_URL` debe apuntar al Gateway correcto (`localhost:5000` en Compose,
  `localhost:8000` para el API local).

## Recuperación básica y límites de las tareas

1. Identifica el servicio afectado con `docker compose ps` y sus logs. Para el
   worker, usa los mismos comandos con `-f compose.yaml -f compose.staging.yaml`.
2. Si el servicio está detenido o degradado, reinicia únicamente el servicio
   afectado; por ejemplo, usa `docker compose restart satellite` o
   `docker compose -f compose.yaml -f compose.staging.yaml restart scientific-worker`.
   Si la causa es Redis, recupera Redis primero y luego Satellite/worker.
3. Comprueba de nuevo `docker compose ps`, el endpoint de salud correspondiente,
   `docker compose exec redis redis-cli ping` y los logs. En el worker busca el
   mensaje de conexión y escucha de cola antes de dar la recuperación por
   confirmada.
4. No reenvíes automáticamente una tarea solo porque falte un log de
   finalización. `scientific-worker` consume con `BRPOP`: al retirar un mensaje
   de la cola no hay reintento automático ni historial duradero del resultado.
   Una interrupción después de retirarlo puede perder esa ejecución; verifica
   con el `task_id` y decide conscientemente si volver a enviarla.

Compose no configura un volumen de Redis ni una política propia de persistencia
de cola; no trates Redis como almacenamiento duradero. Detener o reiniciar el
worker no equivale a recuperar ni reintentar un trabajo que ya consumió. La
descripción detallada de esa cola está en [scientific-worker.md](scientific-worker.md).
