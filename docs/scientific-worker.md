# Worker científico en Redis

El servicio Satellite expone `POST /tasks/measurement-summary`, que encola una
tarea con mediciones numéricas. El proceso `scientific-worker`, ejecutado como
servicio separado, consume la cola Redis `scientific:tasks` y registra el
resumen calculado en sus logs. La respuesta `202` devuelve un identificador de
seguimiento, pero no se almacena el resultado ni se mantiene un historial de
tareas.

## Ejecución con Docker Compose

Desde la raíz del repositorio, el worker está en el override de staging y no en
`compose.yaml` por sí solo. Carga ambos archivos para iniciar el stack:

```powershell
docker compose -f compose.yaml -f compose.staging.yaml up -d --build
```

En otra terminal PowerShell, encola una tarea de ejemplo:

```powershell
Invoke-RestMethod `
  -Uri http://localhost:8002/tasks/measurement-summary `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"measurements":[1.2,2.4,3.6]}'
```

La respuesta contiene `task_id` y `status: queued`. Para observar la ejecución
separada, especifica los dos archivos del Compose de staging:

```powershell
docker compose -f compose.yaml -f compose.staging.yaml logs -f scientific-worker
```

El gateway de la API también reenvía las solicitudes `/api/v1/satellite/*` al
servicio Satellite, de acuerdo con `SATELLITE_SERVICE_URL`.

## Carácter temporal

Compose no declara un volumen para Redis ni configura una política propia de
persistencia. La cola solo actúa como transporte entre el servicio que encola y
el worker; el worker retira la tarea al consumirla. Si el proceso falla después
de retirarla, no hay reintento ni registro permanente del resultado. No se debe
tratar Redis como almacenamiento duradero.

## Correlación entre Gateway, servicios y tareas

El Gateway conserva un `X-Correlation-ID` válido recibido (también acepta
`X-Request-ID` como alias) o genera uno. Lo registra y lo devuelve en la
respuesta. Al usar sus rutas proxy, reenvía el mismo identificador a Satellite
o Scientific. Ambos servicios independientes también lo devuelven en la
respuesta y lo registran en sus logs.

En la cola Redis de `measurement-summary`, Satellite incluye el identificador
en el mensaje. El proceso `scientific-worker` lo conserva y lo escribe en el log
de finalización. Esta cola corresponde al resumen de mediciones; no procesa los
trabajos de `/api/v1/executions`.

Los trabajos de ejecución científica usan `BackgroundTasks` dentro del proceso
FastAPI que atiende la petición. El identificador se pasa al trabajo y aparece
en sus logs de inicio, finalización o error. En particular, el endpoint web
`/api/v1/executions/jobs` es un puente en el proceso Gateway que invoca el
servicio de ejecución directamente; no hace una llamada HTTP al proceso
Scientific ni encola ese trabajo en Redis. Por lo tanto, hay correlación
extremo a extremo en logs para ese flujo, pero no un worker de ejecución
Scientific independiente ni persistencia del identificador en la base de datos.

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
