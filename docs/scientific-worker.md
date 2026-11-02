# Worker científico en Redis

El servicio Satellite expone `POST /tasks/measurement-summary`, que encola una
tarea con mediciones numéricas. El proceso `scientific-worker`, ejecutado como
servicio separado, consume la cola Redis `scientific:tasks` y registra el
resumen calculado en sus logs. La respuesta `202` devuelve un identificador de
seguimiento, pero no se almacena el resultado ni se mantiene un historial de
tareas.

## Partición de evaluación antes del entrenamiento

Para el piloto se eligió una partición temporal por `acquisition_date`: las
fechas se ordenan cronológicamente y el tramo más reciente se reserva para
evaluación (20% de las fechas distintas, con al menos una fecha y sin dejar vacío
el conjunto de entrenamiento). Todos los registros de una misma fecha se
mantienen juntos para evitar fuga temporal. La decisión (`strategy` y
`evaluation_fraction`) forma parte de la configuración requerida del trabajo
de entrenamiento y debe quedar registrada antes de ejecutarlo.

No se eligió una partición por campaña porque el esquema disponible no define
un campo de campaña. Aunque las escenas sí almacenan `acquisition_date`, el CSV
de entrenamiento publicado actualmente solo contiene las variables
`temperatura`, `clorofila_a`, `turbidez` y `ph`. Por tanto, hasta que el origen
de los registros incluya `acquisition_date` y haya al menos dos fechas
distintas, la partición temporal falla explícitamente y el entrenamiento no
debe comenzar. `app.evaluation.split_by_acquisition_date` implementa y valida
esta regla.

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
python -m pip install httpx2 pytest ruff
python -m pytest -q
ruff check .
python -m compileall app tests
```

Las pruebas validan el contrato de encolado, la disponibilidad de Redis, el
rechazo de entradas inválidas y la ejecución de la tarea por el consumidor.
