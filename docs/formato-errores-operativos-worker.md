# Formato de errores operativos del worker científico

Este documento define un contrato objetivo para comunicar y diagnosticar
fallos de los trabajos científicos. Distingue los errores seguros que pueden
persistirse o exponerse de los detalles técnicos que deben quedar únicamente
en logs internos. No cambia el comportamiento actual del servicio.

## Alcance y flujo actual

Los trabajos de `/api/v1/executions` no se procesan en la cola Redis
`scientific:tasks`: el Gateway de la API llama directamente al servicio de
ejecución y este programa `process_scientific_job` con `BackgroundTasks`.
La cola Redis descrita en [Worker científico en Redis](./scientific-worker.md)
es otro flujo (`measurement-summary`) y no persiste el estado de estos jobs.

En el flujo de ejecuciones, un trabajo pasa por `queued`, `running` y un estado
terminal `completed` o `failed`. La tabla `public.scientific_jobs` persiste
`status`, `result`, `error_message`, marcas de tiempo, tipo de trabajo y
organización, entre otros campos. Al fallar, el servicio deja `result` en
`null`, escribe un texto en `error_message` y actualiza `completed_at`.
`GET /api/v1/executions/{job_id}` devuelve el registro mediante `JobStatus`.
Hoy no hay un campo separado `error_code` ni un objeto estructurado `error`.

El Gateway conserva y propaga el `X-Correlation-ID`. Para
`/api/v1/executions/jobs`, el router integrado invoca el servicio directamente
en el mismo proceso; no hay una transformación de error HTTP entre un Gateway
y un proceso Scientific remoto para esta ruta.

## Contrato seguro objetivo

El objeto `error` siguiente es una propuesta de contrato para la respuesta y
persistencia futuras; no representa la forma actual de `JobStatus` ni una
columna existente:

```json
{
  "job_id": "f1b3d8a2-7c54-4b91-8e06-1234567890ab",
  "status": "failed",
  "error": {
    "code": "SCIENTIFIC_INPUT_NOT_FOUND",
    "message": "No se encontró un insumo requerido para ejecutar el trabajo.",
    "retryable": false
  }
}
```

Campos:

| Campo | Uso y restricción |
| --- | --- |
| `job_id` | Identificador del trabajo, sin añadir información de configuración. |
| `status` | Estado terminal permitido para el código; véase el catálogo. |
| `error.code` | Código estable del catálogo, sin IDs, nombres de archivo ni detalles dinámicos. |
| `error.message` | Mensaje operativo seguro, genérico y accionable; no incluir detalles de infraestructura. |
| `error.retryable` | Indica si el sistema puede reintentar automáticamente el mismo trabajo. No equivale a permitir un reintento manual. |

El error seguro no debe incluir stack traces, mensajes crudos de excepciones,
rutas internas, consultas, contenido del insumo, credenciales, tokens, URLs
firmadas, direcciones de servicios ni datos de configuración. El contrato de
error no duplica el `organization_id` ni la configuración del job; esos datos
se consultan bajo los controles de autorización existentes. Los códigos son
identificadores permanentes: si cambia la acción o el significado, se agrega un
código nuevo en lugar de reutilizar uno con otra semántica.

## Catálogo de códigos

| Código seguro | Mensaje seguro | Estado objetivo | Reintentable automáticamente | Acción operativa |
| --- | --- | --- | --- | --- |
| `SCIENTIFIC_INPUT_NOT_FOUND` | `No se encontró un insumo requerido para ejecutar el trabajo.` | `failed` | No. | Revisar que la referencia exista y pertenezca a la organización; comprobar publicación y disponibilidad del archivo/artefacto. Restaurar o volver a publicar el insumo y crear un nuevo job cuando corresponda. Usar este código solo ante ausencia confirmada, no ante una falla transitoria de una dependencia. |
| `SCIENTIFIC_EXECUTION_FAILED` | `No se pudo completar el trabajo científico por un error interno.` | `failed` | No por defecto. | Correlacionar el job con los logs internos, identificar la causa y corregirla. Reintentar solo después de confirmar que la causa es transitoria o fue remediada; no exponer la excepción al cliente. |
| `SCIENTIFIC_JOB_CANCELLED` | `La ejecución del trabajo fue cancelada antes de completarse.` | `cancelled` (objetivo) | No. | Confirmar el origen y motivo de la interrupción, revisar recursos o efectos parciales y crear otro job solo si se requiere continuar. La cancelación no debe provocar un reintento automático. |

Una dependencia inaccesible por un problema transitorio no debe clasificarse
como insumo ausente: hasta contar con una clasificación específica debe
tratarse como `SCIENTIFIC_EXECUTION_FAILED` y su causa permanecer en logs. El
timeout actual también deja el job en `failed`; no se define aquí un cuarto
código para timeout.

## Diagnóstico en logs internos

Cada fallo debe generar un evento estructurado con, al menos, estos campos:

| Campo de log | Contenido |
| --- | --- |
| `timestamp` | Fecha y hora UTC en formato ISO 8601. |
| `correlation_id` | El mismo identificador que el encabezado HTTP `X-Correlation-ID`. |
| `job_id` | Identificador del trabajo afectado. |
| `organization_id` | Organización propietaria, con acceso restringido a logs internos. |
| `job_type` | Tipo del trabajo, por ejemplo `training` o `estimation`. |
| `error_code` | Código estable del catálogo seguro. |
| `failed_stage` | Etapa controlada, por ejemplo `load_input`, `validate`, `compute`, `persist` o `unknown`. |
| `internal_cause` | Excepción/categoría técnica necesaria para diagnóstico; solo en logs internos. Aplicar controles de acceso, retención y redacción de secretos. |

`correlation_id`, `job_id`, `organization_id`, `job_type`, `error_code`,
`failed_stage` y `timestamp` son metadatos de diagnóstico, no campos del error
seguro que recibe el consumidor. `internal_cause` y cualquier stack trace son
exclusivos de logs internos. Aunque el evento de log pueda contener también
`error_code`, este campo no se agrega por ello al registro persistido ni a la
respuesta actual.

Ejemplo de evento de diagnóstico (los valores son ficticios):

```json
{
  "timestamp": "2026-01-15T12:30:45.123Z",
  "level": "ERROR",
  "event": "scientific_job_failed",
  "correlation_id": "corr-demo-001",
  "job_id": "f1b3d8a2-7c54-4b91-8e06-1234567890ab",
  "organization_id": "7a2c9e10-3d44-4f61-8b12-abcdef123456",
  "job_type": "training",
  "error_code": "SCIENTIFIC_INPUT_NOT_FOUND",
  "failed_stage": "load_input",
  "internal_cause": "Training manifest lookup returned no record"
}
```

No copiar valores dinámicos potencialmente sensibles a `internal_cause` sin
redacción. Los ejemplos no contienen credenciales ni datos de usuarios reales.

## Ejemplos por escenario

Los ejemplos muestran la forma segura objetivo y el evento interno asociado.
Las marcas de tiempo e identificadores son sintéticos.

### Insumo ausente

Registro seguro:

```json
{
  "job_id": "f1b3d8a2-7c54-4b91-8e06-1234567890ab",
  "status": "failed",
  "error": {
    "code": "SCIENTIFIC_INPUT_NOT_FOUND",
    "message": "No se encontró un insumo requerido para ejecutar el trabajo.",
    "retryable": false
  }
}
```

Evento de log:

```json
{
  "timestamp": "2026-01-15T12:30:45.123Z",
  "level": "ERROR",
  "event": "scientific_job_failed",
  "correlation_id": "corr-demo-001",
  "job_id": "f1b3d8a2-7c54-4b91-8e06-1234567890ab",
  "organization_id": "7a2c9e10-3d44-4f61-8b12-abcdef123456",
  "job_type": "training",
  "error_code": "SCIENTIFIC_INPUT_NOT_FOUND",
  "failed_stage": "load_input",
  "internal_cause": "Training manifest lookup returned no record"
}
```

### Fallo interno

Registro seguro:

```json
{
  "job_id": "4c8f2a11-6d30-4b74-9a05-1234567890ab",
  "status": "failed",
  "error": {
    "code": "SCIENTIFIC_EXECUTION_FAILED",
    "message": "No se pudo completar el trabajo científico por un error interno.",
    "retryable": false
  }
}
```

Evento de log:

```json
{
  "timestamp": "2026-01-15T12:31:12.456Z",
  "level": "ERROR",
  "event": "scientific_job_failed",
  "correlation_id": "corr-demo-002",
  "job_id": "4c8f2a11-6d30-4b74-9a05-1234567890ab",
  "organization_id": "7a2c9e10-3d44-4f61-8b12-abcdef123456",
  "job_type": "estimation",
  "error_code": "SCIENTIFIC_EXECUTION_FAILED",
  "failed_stage": "compute",
  "internal_cause": "RuntimeError: numerical backend returned an invalid result"
}
```

### Cancelación

Registro seguro objetivo:

```json
{
  "job_id": "9d5a3c20-8e41-4f63-a7b6-1234567890ab",
  "status": "cancelled",
  "error": {
    "code": "SCIENTIFIC_JOB_CANCELLED",
    "message": "La ejecución del trabajo fue cancelada antes de completarse.",
    "retryable": false
  }
}
```

Evento de log:

```json
{
  "timestamp": "2026-01-15T12:32:03.789Z",
  "level": "WARNING",
  "event": "scientific_job_cancelled",
  "correlation_id": "corr-demo-003",
  "job_id": "9d5a3c20-8e41-4f63-a7b6-1234567890ab",
  "organization_id": "7a2c9e10-3d44-4f61-8b12-abcdef123456",
  "job_type": "training",
  "error_code": "SCIENTIFIC_JOB_CANCELLED",
  "failed_stage": "compute",
  "internal_cause": "asyncio.CancelledError"
}
```

## Estado actual y brechas de implementación

Lo descrito en las secciones de contrato y ejemplos es objetivo y aún requiere
implementación. El estado verificable del repositorio es:

- `process_scientific_job` registra inicio, finalización, timeout, límites,
  cancelación y errores. En logs de ejecución se incluyen
  `correlation_id` y `job_id`; los errores internos capturados usan
  `logger.exception`, que adjunta la excepción/traceback.
- El contexto actual de esos eventos no incluye sistemáticamente
  `organization_id`, `job_type`, `error_code` ni `failed_stage`. `extra` añade
  campos al `LogRecord`, pero no hay en el servicio un formato JSON de log
  configurado que garantice su serialización. El logger del worker Redis sí
  define timestamp en su formato de texto, pero su contexto corresponde a
  `task_id` y `correlation_id`, no a los jobs persistidos.
- `scientific_jobs.error_message` es texto y `build_failure_update_payload`
  persiste `status: failed`, `result: null`, `error_message` y `completed_at`.
  `sanitize_error_message` solo normaliza espacios y limita la longitud; no
  elimina rutas, stack traces o secretos. `format_exception_error_message`
  puede persistir directamente el mensaje de la excepción. Por tanto, el texto
  actual no cumple por sí solo el contrato de mensaje seguro.
- El esquema de estado vigente usado por la tabla `public.scientific_jobs`
  permite `queued`, `running`, `completed` y `failed` (migración
  `022_scientific_jobs_idempotency.sql`). No permite `cancelled`, ni existe una
  columna independiente `error_code` o un objeto `error`. La migración
  `019_create_scientific_jobs_table.sql` define una tabla distinta,
  `scientific.jobs`, cuyo enum sí incluye `CANCELLED`; el servicio de ejecución
  inspeccionado consulta `public.scientific_jobs`, por lo que ese enum antiguo
  no habilita la cancelación en la tabla que usa el código actual.
- El contrato OpenAPI científico también documenta los estados `queued`,
  `running`, `completed` y `failed`, además de `error_message`; no refleja aún
  el objeto `error` ni el estado objetivo `cancelled`. Los ejemplos de
  [cliente móvil](./mobile-client-examples.md) muestran el registro actual con
  `error_message`.
- Sí existe manejo de `asyncio.CancelledError`: se registra como cancelación,
  se persiste el estado `failed` con un mensaje de cancelación y se relanza la
  excepción. No se encontró una operación/end-point de cancelación manual del
  job. Para adoptar el estado objetivo `cancelled` habría que cambiar la lógica,
  el esquema/validación del estado y los contratos de respuesta.
- Los errores por insumos ausentes —por ejemplo manifiesto o archivo de
  entrenamiento no encontrado— se convierten hoy en excepciones y se manejan
  por la ruta general de fallo. No existe su código seguro específico ni una
  política explícita de reintento.
- `X-Correlation-ID` se resuelve en middleware y se devuelve en la respuesta;
  el flujo de creación del job lo pasa al procesamiento. La correlación actual
  no se persiste como columna del job.
- El código captura varias familias previstas de excepciones durante la
  ejecución; una excepción que no esté en esas ramas puede propagarse sin
  recorrer la misma ruta de persistencia del fallo. Este contrato no cambia esa
  cobertura.

Antes de exponer o persistir el nuevo objeto seguro, la implementación deberá
incorporar una clasificación controlada de errores, evitar almacenar mensajes
crudos y definir cómo se versiona la respuesta y la persistencia. El manejo de
`internal_cause` en logs también debe evitar que datos sensibles salgan del
ámbito interno.

## Fuentes de verdad inspeccionadas

- [Servicio de ejecución científica](../apps/scientific/app/domains/execution/service_execution.py)
- [Dominio de ejecución y payloads persistidos](../apps/scientific/app/domains/execution/domain_execution.py)
- [Esquemas de ejecución y estados](../apps/scientific/app/domains/execution/schemas_execution.py)
- [Controlador de ejecuciones](../apps/scientific/app/domains/execution/controller_execution.py)
- [Modelo de persistencia de ejecuciones](../apps/scientific/app/domains/execution/model_execution.py)
- [Middleware de correlación Scientific](../apps/scientific/app/main.py)
- [Resolución de correlation ID](../apps/scientific/app/core/correlation.py)
- [Worker Redis independiente](../apps/scientific/app/worker.py)
- [Puente de ejecuciones del Gateway](../apps/api/app/gateway/executions_bridge.py)
- [Middleware de correlación del Gateway](../apps/api/app/main.py)
- [Migración de tabla y estados vigentes](../database/migrations/022_scientific_jobs_idempotency.sql)
- [Migración de organización del job](../database/migrations/023_scientific_jobs_organization_scope.sql)
- [Contrato OpenAPI científico](../contracts/openapi/scientific.yaml)
- [Ejemplos de estado y errores para cliente móvil](./mobile-client-examples.md)
- [Pruebas de fallos y cancelación actuales](../apps/scientific/tests/test_executions.py)
