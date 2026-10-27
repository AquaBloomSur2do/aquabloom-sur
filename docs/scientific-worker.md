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
python -m pip install pytest ruff
python -m pytest -q
ruff check .
python -m compileall app tests
```

Las pruebas validan el contrato de encolado, la disponibilidad de Redis, el
rechazo de entradas inválidas y la ejecución de la tarea por el consumidor.
