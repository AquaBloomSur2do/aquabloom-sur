# Verificación de Despliegue Independiente — Servicio Satellite (`S2-186`)

## 1. Resumen Ejecutivo y Objetivo

Este documento registra el procedimiento reproducible y la evidencia empírica correspondiente a la tarea **[S2-186] Verificar despliegue independiente** (referencia `S2-090`, propuesta revisada v2).

El objetivo técnico consiste en demostrar que el servicio **Satellite** puede reconstruirse, redesplegarse y reiniciarse de forma autónoma mediante Docker Compose sin reconstruir ni reiniciar los servicios **Core** ni **Scientific**.

---

## 2. Arquitectura y Aislamiento de Despliegue

Para habilitar ciclos de vida independientes por microservicio dentro del monorepo, se establecieron los siguientes límites de construcción y ejecución:

| Servicio | Contexto de Build | Dockerfile | Puerto Interno / Host | Endpoint de Salud |
| :--- | :--- | :--- | :--- | :--- |
| `core` | `.` | `apps/api/Dockerfile` | `8001` / `8001` | `GET /api/v1/health` |
| `satellite` | `./apps/satellite` | `Dockerfile` | `8002` / `8002` | `GET /health` |
| `scientific` | `./apps/scientific` | `Dockerfile` | `8003` / `8003` | `GET /api/v1/health` |
| `redis` | Imagen oficial (`redis:7-alpine`) | N/A | `6379` (red interna) | `redis-cli ping` |

### Ajustes de Desacoplamiento Aplicados

1. **Eliminación de dependencia de código entre servicios:** Se removió el import cruzado en `apps/satellite/app/core/auth.py` hacia `apps.api.app.domains.identity.service_identity`, reemplazándolo por una implementación local con idéntico contrato.
2. **Definición de contenedores independientes:**
   - Se incorporaron `apps/scientific/Dockerfile` y `apps/scientific/requirements.txt`.
   - Se actualizaron `apps/satellite/Dockerfile`, `apps/satellite/requirements.txt` y `apps/api/Dockerfile` instalando `libexpat1` (dependencia nativa en tiempo de ejecución de `rasterio`) y fijando `PYTHONPATH=/app`.
   - Se agregó `.dockerignore` en la raíz del repositorio para excluir artefactos locales, entornos virtuales y archivos `.env`.
3. **Orquestación en `compose.yaml`:**
   - Se incorporó el servicio `redis` requerido por el chequeo de salud y la cola de `satellite`.
   - Se corrigieron los `healthcheck` de `gateway`, `core`, `satellite` y `scientific` para consultar sus rutas y puertos reales.
   - `satellite` no declara `depends_on` hacia `core` ni `scientific`, permitiendo ejecutar builds y despliegues aislados con `--no-deps`.
4. **Protección automática contra regresiones:** Se incorporó `apps/satellite/tests/test_independent_deploy.py` para validar por análisis estático (`ast`) que `apps/satellite/app` no importe módulos de `apps.api` ni `apps.scientific`, y que `compose.yaml` mantenga contextos de build y despliegue aislados.

---

## 3. Procedimiento Reproducible

Ejecutar los siguientes pasos desde la raíz del repositorio (`aquabloom-sur`):

### Paso 1: Levantar el conjunto base y registrar estado inicial

```bash
docker compose up -d --build redis core scientific satellite
sleep 15

for svc in core scientific satellite; do
  cid=$(docker compose ps -q "$svc")
  docker inspect --format "$svc | container={{.Id}} | image={{.Image}} | started={{.State.StartedAt}} | health={{.State.Health.Status}}" "$cid"
done

curl -s http://localhost:8001/api/v1/health
curl -s http://localhost:8003/api/v1/health
curl -s http://localhost:8002/health
```

### Paso 2: Reconstruir y redesplegar únicamente `satellite`

```bash
docker compose build --no-cache satellite
docker compose up -d --no-deps --force-recreate satellite
sleep 15

for svc in core scientific satellite; do
  cid=$(docker compose ps -q "$svc")
  docker inspect --format "$svc | container={{.Id}} | image={{.Image}} | started={{.State.StartedAt}} | health={{.State.Health.Status}}" "$cid"
done
```

### Paso 3: Reiniciar únicamente `satellite`

```bash
docker compose restart satellite
sleep 15

for svc in core scientific satellite; do
  cid=$(docker compose ps -q "$svc")
  docker inspect --format "$svc | container={{.Id}} | image={{.Image}} | started={{.State.StartedAt}} | health={{.State.Health.Status}}" "$cid"
done
```

---

## 4. Evidencia Ejecutada y Resultados

- **Fecha de ejecución:** `2026-11-24` (UTC)
- **Entorno:** Docker `29.8.1`, Docker Compose `v5.5.1`

### 4.1 Comparativa de Identificadores de Contenedor, Imagen y Arranque

| Fase | Servicio | Container ID (corto) | Image ID (corto) | `StartedAt` (UTC) | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Inicial** | `core` | `b4d150b29779` | `sha256:cb4897f3d25c` | `2026-11-24T18:54:08.506404937Z` | `healthy` |
| **1. Inicial** | `scientific` | `98328e779dad` | `sha256:d0b0ec2ba42d` | `2026-11-24T18:43:59.14809176Z` | `healthy` |
| **1. Inicial** | `satellite` | `4736b68c0953` | `sha256:fa50d3f4ac9d` | `2026-11-24T18:54:09.004562036Z` | `healthy` |
| **2. Rebuild + Redeploy `satellite`** | `core` | `b4d150b29779` *(sin cambios)* | `sha256:cb4897f3d25c` *(sin cambios)* | `2026-11-24T18:54:08.506404937Z` *(sin cambios)* | `healthy` |
| **2. Rebuild + Redeploy `satellite`** | `scientific` | `98328e779dad` *(sin cambios)* | `sha256:d0b0ec2ba42d` *(sin cambios)* | `2026-11-24T18:43:59.14809176Z` *(sin cambios)* | `healthy` |
| **2. Rebuild + Redeploy `satellite`** | `satellite` | `03261a0ac69b` **(nuevo)** | `sha256:78a02364375d` **(nueva)** | `2026-11-24T18:55:19.958384963Z` **(nuevo)** | `healthy` |
| **3. Restart `satellite`** | `core` | `b4d150b29779` *(sin cambios)* | `sha256:cb4897f3d25c` *(sin cambios)* | `2026-11-24T18:54:08.506404937Z` *(sin cambios)* | `healthy` |
| **3. Restart `satellite`** | `scientific` | `98328e779dad` *(sin cambios)* | `sha256:d0b0ec2ba42d` *(sin cambios)* | `2026-11-24T18:43:59.14809176Z` *(sin cambios)* | `healthy` |
| **3. Restart `satellite`** | `satellite` | `03261a0ac69b` *(mismo)* | `sha256:78a02364375d` *(misma)* | `2026-11-24T18:55:43.089836547Z` **(reiniciado)** | `healthy` |

### 4.2 Salida Exacta de Salud HTTP en las Tres Fases

- **Core (`GET http://localhost:8001/api/v1/health` — HTTP 200):**
  ```json
  {"service":"AquaBloom Sur","version":"v1","status":"degraded","database":{"status":"error","detail":"Fallo de red o permisos insuficientes."}}
  ```
  *(Nota: el estado `degraded` refleja únicamente la ausencia de conexión externa a Supabase en el entorno local de contenedores; el proceso HTTP responde `200 OK` y el contenedor permanece `healthy`.)*

- **Scientific (`GET http://localhost:8003/api/v1/health` — HTTP 200):**
  ```json
  {"service":"AquaBloom Sur Scientific API","version":"v1","status":"ok"}
  ```

- **Satellite (`GET http://localhost:8002/health` — HTTP 200):**
  ```json
  {"service":"aquabloom-satellite","environment":"development","status":"ok","queue":"connected"}
  ```

---

## 5. Conclusión Técnica

La evidencia confirma el cumplimiento íntegro del criterio de aceptación de **S2-186**:

1. Al ejecutar `docker compose build --no-cache satellite` y `docker compose up -d --no-deps --force-recreate satellite`, únicamente `satellite` generó una nueva imagen (`sha256:fa50d3f4ac9d` -> `sha256:78a02364375d`) y un nuevo contenedor (`4736b68c0953` -> `03261a0ac69b`).
2. Al ejecutar `docker compose restart satellite`, únicamente `satellite` actualizó su marca de arranque (`18:55:19Z` -> `18:55:43Z`) y recuperó el estado `healthy` con conexión activa a Redis (`"queue":"connected"`).
3. En todas las fases, `core` y `scientific` mantuvieron intactos sus identificadores de imagen, contenedores y timestamps `StartedAt`, confirmando ausencia total de reconstrucción o reinicio colateral.


