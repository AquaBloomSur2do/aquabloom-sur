# Worker científico en Redis

El servicio Satellite expone `POST /tasks/measurement-summary`, que encola una
tarea con mediciones numéricas. El proceso `scientific-worker`, ejecutado como
servicio separado, consume la cola Redis `scientific:tasks` y registra el
resumen calculado en sus logs. La respuesta `202` devuelve un identificador de
seguimiento, pero no se almacena el resultado ni se mantiene un historial de
tareas.

## Ejecución con Docker Compose

Desde la raíz del repositorio:

```powershell
docker compose up --build
```

En otra terminal PowerShell, encola una tarea de ejemplo:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8001/tasks/measurement-summary `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"measurements":[1.2,2.4,3.6]}'
```

La respuesta contiene `task_id` y `status: queued`. Para observar la ejecución
separada:

```powershell
docker compose logs -f scientific-worker
```

El gateway de la API también reenvía las solicitudes `/api/v1/satellite/*` al
servicio Satellite, de acuerdo con `SATELLITE_SERVICE_URL`.

## Persistencia del artefacto de modelo

El servicio que completa un trabajo de entrenamiento puede registrar el
artefacto mediante `POST /api/v1/executions/{job_id}/artifact`, autenticándose
con `X-Internal-Token` y enviando un multipart `file`. La API valida que el
identificador corresponda a un trabajo `training`, limita el archivo a 100 MiB
y calcula su checksum SHA-256.

Los trabajos científicos se guardan en `scientific_jobs` y su estado se consulta
con `GET /api/v1/executions/{job_id}`. Esto permite conservar la relación del
artefacto aunque la API se reinicie.

El archivo se almacena en el bucket privado `model_artifacts`. PostgreSQL
registra su nombre, tipo MIME, tamaño, checksum, ruta de Storage y
`training_job_id` como clave foránea a `scientific_jobs`. Se permite repetir la
carga del mismo contenido sin crear duplicados; reemplazar un artefacto ya
asociado a ese entrenamiento responde `409`.

La metadata persistida se consulta con
`GET /api/v1/executions/{job_id}/artifact`, también usando `X-Internal-Token`.
Las migraciones que crean la tabla y el bucket están en
`database/migrations/20261028_create_model_artifacts.sql` y
`supabase/migrations/20261028_create_model_artifacts.sql`.

## Carácter temporal

Redis se inicia con RDB y AOF desactivados y no tiene un volumen persistente.
La cola solo actúa como transporte entre el servicio que encola y el worker; el
worker retira la tarea al consumirla. Si el proceso falla después de retirarla,
no hay reintento ni registro permanente, lo cual mantiene el alcance mínimo de
esta integración.

## Comprobaciones locales

Desde `apps/satellite`:

```powershell
python -m pip install -r requirements.txt
python -m pip install httpx2 pytest ruff
python -m pytest -q
ruff check .
python -m compileall app tests
```

Las pruebas validan el contrato de encolado, la disponibilidad de Redis, el
rechazo de entradas inválidas y la ejecución de la tarea por el consumidor.
