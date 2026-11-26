# Contextos de autorización en staging (S3-22)

**Ticket:** AQU-373 (`S3-22`)  
**Contexto:** Sprint 3 · Semana 1 — Contratos y base de cierre.  
Define dos contextos de autorización independientes en staging para validar
aislamiento multi-organización, permisos de consulta y pruebas de integración
(`S3-70`, `S3-86`, `S3-93`).

> **Seguridad:** nunca guardar contraseñas, JWT ni llaves de Supabase en este
> documento ni en el repositorio. Las credenciales se obtienen del gestor
> aprobado del equipo o del flujo de autenticación de staging y se mantienen
> solo en variables de entorno locales.

## 1. Cuentas y organizaciones de prueba

Crear o verificar las organizaciones y cuentas en staging mediante los flujos
administrativos aprobados de Core/Supabase Auth. Cada cuenta debe tener una
sola membresía activa y no debe pertenecer a la otra organización.

| Contexto | Organización | `organization_id` (staging) | Cuenta de prueba | Rol de biblioteca |
| :--- | :--- | :--- | :--- | :--- |
| **Contexto A** | Org A — Piloto Villarrica | `<UUID_ORG_A>` | `qa-org-a@aquabloom.test` | `author`, miembro activo |
| **Contexto B** | Org B — Piloto Llanquihue | `<UUID_ORG_B>` | `qa-org-b@aquabloom.test` | `author`, miembro activo |

Verificaciones antes de probar:

1. Org A y Org B existen, tienen UUID distintos y están activas.
2. Los dos usuarios existen en Supabase Auth y están activos.
3. La membresía de A está activa solo en Org A; la de B, solo en Org B.
4. Existe al menos un trabajo y una predicción por organización, con sus
   identificadores registrados en el gestor de pruebas del equipo.
5. Para la biblioteca, crear borradores de prueba cuando los endpoints de
   biblioteca estén disponibles. No registrar identificadores personales ni
   credenciales en este archivo.

Los UUID de la tabla son placeholders hasta que alguien con acceso a staging
los consulte y los reemplace. No inventar UUID ni copiar identificadores de
producción.

## 2. Obtener credenciales de forma segura

Configura la URL y los UUID en tu sesión de Git Bash. Obtén cada JWT mediante
el flujo de login aprobado o el gestor de secretos del equipo; no lo escribas
como literal en un comando:

```bash
export STAGING_API_URL="https://<gateway-staging>"
export STAGING_ORG_A_ID="<UUID_ORG_A>"
export STAGING_ORG_B_ID="<UUID_ORG_B>"

read -rsp "JWT de Org A: " STAGING_TOKEN_ORG_A; echo
export STAGING_TOKEN_ORG_A
read -rsp "JWT de Org B: " STAGING_TOKEN_ORG_B; echo
export STAGING_TOKEN_ORG_B
```

Al terminar las pruebas, elimina los tokens de esa sesión:

```bash
unset STAGING_TOKEN_ORG_A STAGING_TOKEN_ORG_B
```

## 3. Matriz de recursos consultables por contexto

| Recurso | Contexto A (Org A) | Contexto B (Org B) | Comportamiento esperado |
| :--- | :---: | :---: | :--- |
| Catálogo público | Permitido (`200 OK`) | Permitido (`200 OK`) | No depende de la organización autenticada. |
| Escenas de lago (`GET /api/v1/lakes/{lake_id}/scenes`) | Permitido (`200 OK`) | Permitido (`200 OK`) | La ruta actual es pública y consulta por lago/fechas; no usarla como prueba de aislamiento organizacional. |
| Trabajo de Org A (`GET /api/v1/executions/{job_id}`) | Permitido (`200 OK`) | Denegado (`403` o `404`) | Requiere JWT y `X-Organization-ID`; el trabajo se consulta dentro de la organización indicada. |
| Predicción de Org A (`GET /api/v1/scientific/api/v1/predictions/{prediction_id}`) | Permitido (`200 OK`) | Denegado (`403` o `404`) | Requiere JWT, membresía activa y `X-Organization-ID`; el detalle se filtra por organización. |
| Trabajo de Org B | Denegado (`403` o `404`) | Permitido (`200 OK`) | Aislamiento por organización. |
| Predicción de Org B | Denegado (`403` o `404`) | Permitido (`200 OK`) | Aislamiento por organización. |
| Borrador de biblioteca (`draft`) de Org A u Org B | Solo su organización | Denegado a la otra (`403` o `404`) | Política prevista por S3-05; verificar cuando estén disponibles las rutas de biblioteca. |
| Versión publicada de biblioteca | Permitido según catálogo | Permitido según catálogo | La publicación no debe exponer borradores ni saltarse las reglas de acceso del catálogo. Confirmar con el endpoint implementado. |

En las rutas de trabajos y predicciones, usa el mismo `organization_id` para
el que el usuario tiene membresía activa. Un `404` para un recurso ajeno es
aceptable si el servicio oculta su existencia; un `403` también es aceptable
cuando el servicio informa explícitamente la falta de autorización.

## 4. Comprobación mínima en staging

Consulta un recurso conocido de Org A. La ruta de predicciones se publica a
través del proxy del Gateway bajo `/api/v1/scientific/`; requiere
`X-Organization-ID` además del JWT:

```bash
export PREDICTION_ID_ORG_A="<UUID_PREDICTION_A>"

# A consulta una predicción de A: esperado 200 OK.
curl -i "$STAGING_API_URL/api/v1/scientific/api/v1/predictions/$PREDICTION_ID_ORG_A" \
  -H "Authorization: Bearer $STAGING_TOKEN_ORG_A" \
  -H "X-Organization-ID: $STAGING_ORG_A_ID" \
  -H "Accept: application/json"

# B presenta su propia organización para consultar la predicción de A:
# esperado 404 Not Found (recurso no visible en Org B).
curl -i "$STAGING_API_URL/api/v1/scientific/api/v1/predictions/$PREDICTION_ID_ORG_A" \
  -H "Authorization: Bearer $STAGING_TOKEN_ORG_B" \
  -H "X-Organization-ID: $STAGING_ORG_B_ID" \
  -H "Accept: application/json"

# B intenta declarar Org A: esperado 403 Forbidden o 404 Not Found.
curl -i "$STAGING_API_URL/api/v1/scientific/api/v1/predictions/$PREDICTION_ID_ORG_A" \
  -H "Authorization: Bearer $STAGING_TOKEN_ORG_B" \
  -H "X-Organization-ID: $STAGING_ORG_A_ID" \
  -H "Accept: application/json"
```

Repite la misma comprobación con el trabajo de Org A en
`/api/v1/executions/<JOB_ID_ORG_A>`. Guarda los códigos HTTP y los UUID de
staging como evidencia de prueba fuera de este repositorio, sin incluir tokens,
contraseñas ni llaves.
