# Contrato Candidato de Estimaciones y Trabajos Científicos (`S3-02`)

**Fecha:** 26 de noviembre de 2026  
**Estado:** Candidato para acuerdo entre Backend (Gateway / Scientific), Web y Móvil  
**Insumo para:** `AQU-234` (`[S2-180] Verificar respuestas reales contra OpenAPI`)  
**Especificación OpenAPI candidata:** `contracts/openapi/estimations-jobs-candidate.yaml`  
**Fuentes auditadas:** `apps/api/app/main.py`, `apps/api/app/gateway/controller_gateway.py`, `apps/api/app/gateway/executions_bridge.py`, `apps/scientific/app/main.py`, `apps/scientific/app/domains/execution/*`, `apps/scientific/app/domains/prediction/*`, `contracts/openapi/scientific.yaml`, `apps/api/tests/test_openapi_contracts.py`, `apps/web/src/services/executions.ts`, `apps/web/src/services/models.ts` y `docs/mobile-client-examples.md`.

---

## 1. Objetivo y Alcance

Este documento fija el **contrato candidato único** para las operaciones de trabajos científicos (`training` y `estimation`), acceso a artefactos y consulta detallada de estimaciones consumidas por los clientes **Web** (React + TypeScript) y **Móvil** (React Native) a través del **API Gateway**, sin crear una API paralela para móvil.

El documento cubre:
1. Catálogo de rutas públicas acordadas y rutas internas servicio-a-servicio.
2. Cabeceras obligatorias, permisos, aislamiento multi-organización y códigos de estado HTTP.
3. Esquemas candidatos de entrada/salida y máquina de estados de trabajos y modelos.
4. Registro de discrepancias por ruta entre Gateway, `scientific`, `contracts/openapi/scientific.yaml`, Web y Móvil.
5. Insumo técnico verificable para ampliar `apps/api/tests/test_openapi_contracts.py` (`AQU-234` / `S2-180`).

---

## 2. Reglas Transversales del Contrato

### 2.1 Cabeceras Estándar

| Cabecera | Sentido | Obligatoriedad | Regla de Contrato |
| --- | --- | --- | --- |
| `Authorization` | Request | Obligatoria en todas las rutas de este dominio | Formato `Bearer <JWT>` emitido por Supabase Auth. El `sub` debe ser un UUID válido. |
| `X-Organization-ID` | Request | Obligatoria en `/executions/*` y `/predictions/{id}` | UUID de la organización activa del usuario. Define el aislamiento multi-tenant. |
| `X-Idempotency-Key` | Request | Opcional en creación de trabajos (`POST`) | Texto no vacío tras `.strip()`, máximo 255 caracteres. Alcance por `(organization_id, idempotency_key)`. |
| `X-Correlation-ID` | Request / Response | Opcional en entrada; obligatoria en salida | Propagada desde el cliente (o `X-Request-ID`) o generada como UUID por Gateway/Scientific. Expuesta por CORS (`Access-Control-Expose-Headers`). |
| `X-Internal-Token` | Request | Exclusiva para rutas internas servicio-a-servicio | Prohibido su uso desde clientes Web o Móvil. |
| `Cache-Control` | Response | Obligatoria en `GET /api/v1/executions/{job_id}/artifact` | Valor estricto `no-store` para proteger enlaces firmados temporales. |

### 2.2 Estructura de Errores

Los clientes Web y Móvil deben decidir siempre por el **código HTTP** y tolerar la estructura de error del runtime FastAPI:

- **Errores HTTP generales (`401`, `403`, `404`, `409`, `502`, `503`):** `{"error": "HTTP Error" | "Not Found", "message": "<detalle>"}`.
- **Errores de validación de esquema (`422`):** `{"error": "Validation Error", "message": "Parámetros de entrada inválidos", "details": [...]}`.
- **Dependencia caída en proxy del Gateway (`503`):** `{"error": "ServiceUnavailable", "message": "La dependencia solicitada no está disponible.", "details": null}`.

---

## 3. Catálogo de Rutas, Permisos y Estados Acordados

### 3.1 Rutas Públicas Acordadas (Gateway → Web y Móvil)

| Método y Ruta Pública | Consumidores | Autenticación y Permisos | Códigos de Éxito / Error |
| --- | --- | --- | --- |
| `POST /api/v1/executions/jobs` | Web, Móvil | `Authorization` + `X-Organization-ID` + membresía activa en la organización | `202` / `401`, `404`, `409`, `422`, `500`, `502`, `503` |
| `GET /api/v1/executions/{job_id}` | Web, Móvil | `Authorization` + `X-Organization-ID` + membresía activa; respuesta opaca `404` fuera de la organización | `200` / `401`, `404`, `422`, `503` |
| `GET /api/v1/executions/{job_id}/artifact` | Web, Móvil | `Authorization` + `X-Organization-ID` + membresía activa; enlace temporal con `Cache-Control: no-store` | `200` / `401`, `404`, `422`, `503` |
| `GET /api/v1/predictions/{prediction_id}` *(candidata a exposición directa en Gateway)* | Web, Móvil | `Authorization` + `X-Organization-ID` + membresía activa + rol (`admin`, `administrador`, `supervisor`, `investigador`, `auditor`) o permiso `predictions:read` / `catalog:read` | `200` / `401`, `403`, `404`, `422`, `502`, `503` |
| `GET /api/v1/models?lake_id={lake_id}` *(candidata a formalizar en Gateway)* | Web (`EstimationForm`), Móvil | `Authorization` (y organización activa si aplica al catálogo de modelos del tenant) | `200` / `401`, `403`, `422`, `503` |

### 3.2 Rutas Internas (Solo Servicio a Servicio — No para Web/Móvil)

| Método y Ruta Interna | Servicio Propietario | Autenticación y Permisos | Códigos de Éxito / Error |
| --- | --- | --- | --- |
| `POST /api/v1/executions/` | `scientific` | `X-Internal-Token` + `Authorization` + `X-Organization-ID` + membresía activa | `202` / `401`, `404`, `409`, `422`, `500`, `502`, `503` |
| `POST /api/v1/predictions/` | `scientific` | `X-Internal-Token` (persistencia inmutable de resultados) | `201` / `401`, `404`, `422`, `502`, `503` |

### 3.3 Estados y Transiciones Acordadas

- **Ciclo de vida de trabajos (`JobStatus.status`):**
  - `queued` → `running` → `completed`
  - `queued` → `running` → `failed`
  - **Regla de polling (Web y Móvil):** consultar `GET /api/v1/executions/{job_id}` únicamente mientras `status ∈ {queued, running}`; detener el polling al recibir `completed`, `failed`, `401`, `403` o `404`.
- **Tipos de trabajo (`job_type`):**
  - **Contrato público (`POST /api/v1/executions/jobs`):** acepta `training` y `estimation` (acepta mayúsculas `TRAINING`/`ESTIMATION` por compatibilidad de clientes y normaliza a minúsculas en la persistencia y en `JobStatus.job_type`).
  - **Valor `modeling`:** presente en el enum `ScientificJobType` por compatibilidad histórica, pero **fuera de alcance** del flujo público del piloto.
- **Estados de modelos aptos para estimación (`ModelConfig.status`):**
  - Aptos para selección en UI y ejecución: `EXPERIMENTAL`, `VALIDATED` (y `ACTIVE` en validación de dominio `ModelScopeSpec`).
  - Rechazados para estimación: `DEPRECATED`, `REJECTED`, `ARCHIVED`, `DRAFT`.

---

## 4. Esquemas Candidatos Acordados

### 4.1 Creación de Trabajo (`POST /api/v1/executions/jobs`)

- **Request `training`:**
  - `job_type`: `"training"` (o `"TRAINING"` por compatibilidad).
  - `dataset_version_id`: UUID opcional en nivel superior si no se envía `config.version_id`.
  - `config`: `{ dataset_id?: UUID, version_id?: UUID, epochs?: int (>0, default 100), learning_rate?: float (>0, default 0.001) }`. Al menos `dataset_version_id` o `config.version_id` debe estar presente y corresponder a una versión en estado `PUBLISHED` (`409` en caso contrario).
- **Request `estimation`:**
  - `job_type`: `"estimation"` (o `"ESTIMATION"` por compatibilidad).
  - `config`: `{ model_id: UUID, scene_id: UUID, points?: InferencePoint[] (min 1, máx operativo 100), model_name?: string (no vacío), model_version_id?: UUID, training_job_id?: UUID, dataset_id?: UUID, dataset_version_id?: UUID }`.
- **Response `202 Accepted` (`JobResponse`):**
  - `{ job_id: UUID, status: "queued" | string, status_url: "/api/v1/executions/{job_id}", message: string }`.

### 4.2 Estado y Resultado de Trabajo (`GET /api/v1/executions/{job_id}`)

- **Envoltorio `JobStatus` (`200 OK`):**
  - Campos obligatorios: `job_id` (UUID), `job_type`, `status`, `config` (objeto), `created_at` (date-time).
  - Campos opcionales/anulables: `result`, `traceability_evidence` (`TraceabilityEvidence`), `dataset_version_id`, `model_version_id`, `scene_id`, `requested_by`, `error_message`, `started_at`, `completed_at`, `updated_at`.
- **Variante `result` para `job_type = "training"` (`TrainingResult`):**
  - `model`, `baseline` (`BaselineInfo`), `prediction_value`, `predictions` (`number[]`), `metrics` (`{ mae, rmse }`), `version`, `dataset_version_id`, `model_version_id`, `reproducibility` (`ReproducibilityMetadata`), `provenance` (`DatasetProvenanceInfo`), `limitations` (`string[]`), `status`, `warnings` (`string[]`) y referencia opcional `model_artifact`.
- **Variante `result` para `job_type = "estimation"` (`EstimationResult` candidato):**
  - Con inferencia por puntos: `model_id`, `scene_id`, `model_type` (`"baseline" | "linear"`), `artifact_checksum` (SHA-256 hex 64), `point_count`, `predictions` (`PointPredictionItem[]`), `baseline?`, y campos de evidencia de origen (`model_name`, `model_version_id`, `training_job_id`, `dataset_id`, `dataset_version_id`).
  - Sin `points` con origen verificado: `status: "completed"`, `scene_id` y campos de evidencia de origen.
  - Modo legacy sin `points` ni origen: `{"message": "Tipo de trabajo 'estimation' no implementado aún."}`.

### 4.3 Acceso a Artefacto (`GET /api/v1/executions/{job_id}/artifact`)

- **Response `200 OK` (`ModelArtifactAccess`):** `{ job_id: UUID, download_url: string (uri), expires_in: int (>0, default 60), checksum?: string | null, size_bytes?: int | null }`.

### 4.4 Detalle de Estimación Persistida (`GET /api/v1/predictions/{prediction_id}`)

- **Response `200 OK` (`PredictionDetailResponse`, sin campos extra):**
  - `id`, `organization_id`, `variable`, `unit`, `status`, `points` (`EstimationPoint[]`), `provenance` (`EstimationProvenance` con `model_version_id`, `model_name`, `training_job_id`, `scene_id`, `lake_id`, `scene_identifier`, `acquisition_date`, `dataset_id`, `dataset_version_id`, `rules`, `generated_at`), `warnings`, `usage_limits`, `created_at`.

---

## 5. Registro de Discrepancias por Ruta

| Ruta | Estado Real (Gateway / `scientific`) | Estado en `contracts/openapi/scientific.yaml` y `S2-180` | Estado en Web y Móvil | Acción Acordada |
| --- | --- | --- | --- | --- |
| `POST /api/v1/executions/jobs` | Montada en Gateway (`executions_bridge.py`). Acepta `job_type` en mayúsculas/minúsculas y `config: dict` genérico validado en runtime. Exige UUID en `model_id`/`scene_id`. | **Ausente** en `scientific.yaml` y **sin prueba** en `test_openapi_contracts.py` (`S2-180`). El OpenAPI generado por FastAPI muestra `config: object` sin subesquemas. | Web (`executions.ts`) envía `TRAINING`/`ESTIMATION`. Móvil (`mobile-client-examples.md`) documenta minúsculas y aclara compatibilidad. | Incorporar ruta y unión explícita de configuraciones en el contrato candidato y añadir test en `test_openapi_contracts.py`. |
| `POST /api/v1/executions/` | Montada en `scientific` **y también expuesta en `apps/api/app/main.py`**. Exige `X-Internal-Token`. Acepta `modeling` y `model_id`/`scene_id` como `str` libre. | **Ausente** en `scientific.yaml`. Cubierta en `test_openapi_contracts.py` (`202`), pero contra la ruta interna. | Web no la usa. Móvil prohíbe su uso por requerir `X-Internal-Token`. | Mantenerla estrictamente como ruta interna; evitar que clientes públicos la consuman y documentar la diferencia de validación (`str` vs. `UUID`) hasta retirar el modo legacy. |
| `GET /api/v1/executions/{job_id}` | Montada en Gateway y `scientific`. Devuelve `JobStatus` con `scene_id`, `traceability_evidence`, `reproducibility`, `provenance`, `limitations` y resultado de estimación. Devuelve `404` opaco ante membresía inactiva. | **Desactualizada** en `scientific.yaml`: faltan `scene_id`, `traceability_evidence`, `reproducibility`, `provenance`, `limitations` y el esquema de `EstimationResult`. `S2-180` solo valida `training` básico (sin `estimation` ni `traceability_evidence`). | Web (`executions.ts`) mezcla `training` y `estimation` en `TrainingJobResult` y aún no tipa `traceability_evidence`. Móvil sigue indicando en sección 3.4 que `estimation` nunca ejecuta inferencia. | Actualizar `scientific.yaml` desde el contrato candidato, ampliar `S2-180` con `estimation` y `traceability_evidence`, tipar unión discriminada en Web y actualizar sección 3.4 de `mobile-client-examples.md`. |
| `GET /api/v1/executions/{job_id}/artifact` | Montada en `scientific` y en Gateway (`execution_router`). Devuelve `ModelArtifactAccess` con `Cache-Control: no-store`. | **Ausente** en `scientific.yaml` y **sin prueba** en `test_openapi_contracts.py`. | Web (`ScientificJobDetail.tsx`) mantiene el botón *"Abrir artefacto"* deshabilitado indicando que la API no lo expone. Móvil no la documenta. | Formalizar la ruta en el contrato OpenAPI, cubrirla en `S2-180` y habilitar el consumo en Web/Móvil en Sprint 3. |
| `GET /api/v1/predictions/{prediction_id}` | Montada **solo en `scientific`**, NO en `apps/api/app/main.py`. Solo accesible vía proxy `/api/v1/scientific/api/v1/predictions/{prediction_id}` (`include_in_schema=False`). Exige roles/permisos (`403`), distinto del `404` de `/executions/{job_id}`. | **Ausente** en `/openapi.json` del Gateway, **ausente** en `scientific.yaml` y **sin prueba** en `test_openapi_contracts.py` (`S2-180` solo prueba `POST /api/v1/predictions/`). | Web no la consume. Móvil (`mobile-client-examples.md`) la marca como ruta pendiente de confirmación de prefijo por backend. | Decidir en Sprint 3 su exposición explícita en Gateway (o prefijo documentado `/api/v1/predictions/{prediction_id}`), unificar criterio de permisos/errores y añadir validación en `S2-180`. |
| `POST /api/v1/predictions/` | Montada solo en `scientific`, protegida por `X-Internal-Token` (`201 Created`). | **Ausente** en `scientific.yaml`. Cubierta en `test_openapi_contracts.py` sobre `scientific_client`. | No aplica a Web ni Móvil (operación interna del worker). | Mantener catalogada como interna en la especificación de `scientific` y fuera de la superficie pública de Web/Móvil. |
| `GET /api/v1/models?lake_id={lake_id}` | **No implementada ni montada** en `apps/api/app/main.py` ni en `apps/scientific/app/main.py` (aunque `scientific` monta `model_scope_router` sin exposición pública en Gateway). | **Ausente** en `/openapi.json` del Gateway, `scientific.yaml` y `test_openapi_contracts.py`. | Web (`apps/web/src/services/models.ts`) la invoca activamente desde `EstimationForm.tsx` esperando `ModelConfig[]`. Móvil no la documenta. | **Brecha crítica:** acordar si el Gateway expondrá `GET /api/v1/models?lake_id={lake_id}` con el esquema `ModelConfig[]` (incluyendo `model_version_id`, `training_job_id`, `dataset_id`, `dataset_version_id`) antes de cerrar la integración E2E del Sprint 3. |
| `/api/v1/scientific/{path:path}` (proxy) | Registrada con `include_in_schema=False` en `controller_gateway.py`. Además, `apps/api/app/main.py` monta `execution_router` directamente in-process, generando doble vía de acceso (`/api/v1/executions/*` vs. `/api/v1/scientific/api/v1/executions/*`). | Invisibilizada en `/openapi.json` del Gateway; `S2-180` no puede auditar rutas que solo vivan detrás del proxy. | Web usa `/api/v1/executions/*`. Móvil advierte no asumir rutas no listadas en `/openapi.json` del Gateway. | Fijar `/api/v1/executions/*` y `/api/v1/predictions/*` como prefijos públicos canónicos documentados en OpenAPI del Gateway y evitar que clientes consuman rutas sin esquema. |

---

## 6. Insumo Directo para `AQU-234` (`[S2-180] Verificar respuestas reales contra OpenAPI`)

La suite actual `apps/api/tests/test_openapi_contracts.py` ya valida 4 escenarios (`GET /api/v1/scenes`, `GET /api/v1/datasets/versions/{version_id}/training-file`, `POST /api/v1/executions/` + `GET /api/v1/executions/{job_id}` en `training` y `POST /api/v1/predictions/`).

A partir de este contrato candidato (`contracts/openapi/estimations-jobs-candidate.yaml`), la siguiente iteración de pruebas en `test_openapi_contracts.py` debe cubrir los **5 huecos detectados**:

1. **`POST /api/v1/executions/jobs` (`202`):** verificar la respuesta real del puente público del Gateway tanto para `job_type: "training"` como para `job_type: "estimation"` (con metadatos de origen y `points`).
2. **`GET /api/v1/executions/{job_id}` (`200`) en modo `estimation` y con `traceability_evidence`:** validar `scene_id`, `traceability_evidence`, `predictions` por punto y evidencia de origen (`training_job_id`, `dataset_id`, `dataset_version_id`, `model_name`).
3. **`GET /api/v1/executions/{job_id}` (`200`) en modo `training` completo:** validar `reproducibility`, `provenance` y `limitations` además de `metrics` y `baseline`.
4. **`GET /api/v1/executions/{job_id}/artifact` (`200`):** validar el esquema `ModelArtifactAccess` y la presencia de la cabecera `Cache-Control: no-store`.
5. **`GET /api/v1/predictions/{prediction_id}` (`200`):** validar la respuesta real de `PredictionDetailResponse` (incluyendo `points`, `provenance`, `warnings` y `usage_limits`) contra el esquema OpenAPI de `scientific` (y del Gateway una vez expuesta la ruta).

---

## 7. Criterios de Validación para Acuerdo con Web y Móvil

- [ ] Confirmar con Web y Móvil el uso exclusivo de `POST /api/v1/executions/jobs`, `GET /api/v1/executions/{job_id}` y `GET /api/v1/executions/{job_id}/artifact` para el flujo de trabajos.
- [ ] Definir en equipo si `GET /api/v1/predictions/{prediction_id}` se expone directamente en el Gateway o se consolida en `JobStatus.result`.
- [ ] Resolver la brecha de `GET /api/v1/models?lake_id={lake_id}` requerida por `EstimationForm.tsx`.
- [ ] Sincronizar `contracts/openapi/scientific.yaml` con `contracts/openapi/estimations-jobs-candidate.yaml` una vez aprobadas las definiciones y activar los 5 casos de verificación adicionales en `apps/api/tests/test_openapi_contracts.py`.

