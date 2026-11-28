# Contrato de revisión de versiones de biblioteca (S3-11)

**Ticket:** `S3-11`  
**Contexto:** Sprint 3 · Semana 1 — Contratos y base de cierre.

Este contrato define la solicitud, la identificación del revisor, la decisión,
el motivo, los errores y los efectos de estado para revisar una versión
concreta de un recurso de biblioteca (`version_id`). Sirve como especificación
base antes de implementar la persistencia y los endpoints del dominio `library`
(`S3-36`, `S3-68`).

---

## 1. Separación respecto al flujo de Dataset

El flujo de revisión de versiones de biblioteca es independiente del dominio de
Dataset:

- **Dataset (`POST /api/v1/datasets/memberships/{membership_id}/decisions`):**
  evalúa la inclusión o exclusión de una pertenencia (`membership_id`) dentro de
  un dataset candidato y persiste registros en `dataset.decisions`.
- **Biblioteca (`POST /api/v1/library/versions/{version_id}/reviews`):**
  evalúa una versión concreta (`version_id`) de un recurso de biblioteca que fue
  enviada a revisión (`submitted`), gobierna su transición hacia `approved` o
  `draft` (según `docs/library-version-transitions.md`) y **no** reutiliza
  `dataset.decisions` ni los esquemas o endpoints de `/api/v1/datasets/`.

---

## 2. Endpoint, autenticación y permisos

- **Método y ruta:** `POST /api/v1/library/versions/{version_id}/reviews`
- **Autenticación:** obligatoria mediante sesión autenticada (token Bearer JWT válido).
- **Resolución de organización:** el cliente **no** envía `X-Organization-ID`;
  el servidor resuelve la organización propietaria directamente a partir de
  `version_id` (mediante el recurso padre en biblioteca) y verifica que el
  usuario autenticado posea una membresía activa en dicha organización.
- **Roles autorizados:** `reviewer` u `org_admin` dentro de la organización
  propietaria del recurso (alineado con `docs/library-version-transitions.md`).
- **Regla de no auto-revisión:** el autor de la versión (o quien ejecutó el
  envío a revisión) **no** puede revisar su propia versión, incluso si posee rol
  `reviewer` u `org_admin` en la organización (`403 Forbidden`).
- **Precondición de estado:** la versión objetivo (`version_id`) debe existir,
  pertenecer a la organización del usuario y encontrarse exactamente en estado
  `submitted`.

### Identificación del revisor

- El identificador del revisor (`reviewer_id`) se obtiene **exclusivamente** de
  la sesión autenticada en el servidor (`sub` del JWT).
- El cuerpo de la solicitud **no** admite `reviewer_id`, `user_id` ni
  `reviewed_by`; si el cliente envía esos campos, la solicitud se rechaza con
  `422 Unprocessable Entity` para impedir suplantación de identidad.

---

## 3. Solicitud (`Request`)

### Parámetro de ruta

| Parámetro | Tipo | Regla |
| :--- | :--- | :--- |
| `version_id` | `UUID` | Identificador único de la versión concreta de biblioteca en estado `submitted`. |

### Cuerpo JSON (`application/json`)

| Campo | Tipo | Obligatorio | Regla |
| :--- | :--- | :--- | :--- |
| `decision` | `string` | Sí | Solo admite `"approved"` o `"changes_requested"`. |
| `reason` | `string` | Sí | Cadena entre `1` y `1000` caracteres (`min_length=1`, `max_length=1000`), no compuesta solo por espacios; se normaliza recortando espacios extremos (`trim`) antes de persistir. |

> No se permiten propiedades adicionales en el objeto de solicitud (`extra="forbid"`).

### Ejemplos de solicitud

**Aprobar versión (`decision: "approved"`):**

```json
{
  "decision": "approved",
  "reason": "Atribución SPDX verificada, metadatos completos y archivo CSV íntegro."
}
```

**Solicitar cambios (`decision: "changes_requested"`):**

```json
{
  "decision": "changes_requested",
  "reason": "El identificador de la estación no coincide con el catálogo oficial y falta describir las variables medidas en el CSV."
}
```

---

## 4. Respuesta exitosa (`201 Created`)

- **Cabecera estándar:** incluye `X-Correlation-ID` en todas las respuestas
  exitosas y de error (RNF-25).
- **Historial inmutable:** cada revisión crea un nuevo registro histórico
  inmutable (`review_id`), permitiendo múltiples ciclos de revisión sobre una
  misma versión (`submitted` -> `draft` -> `submitted` -> `approved`).
- **Concurrencia:** la transición de estado de la versión se ejecuta de forma
  atómica; ante dos revisiones concurrentes sobre una misma versión en estado
  `submitted`, solo la primera prospera (`201 Created`) y la segunda recibe
  `409 Conflict` (`INVALID_VERSION_TRANSITION`).

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `review_id` | `UUID` | Identificador único del registro de revisión generado. |
| `version_id` | `UUID` | Identificador de la versión de biblioteca evaluada. |
| `reviewer_id` | `UUID` | Identificador del usuario revisor derivado de la sesión autenticada. |
| `decision` | `string` | `"approved"` o `"changes_requested"`. |
| `reason` | `string` | Motivo normalizado (`trim`) registrado por el revisor. |
| `previous_status` | `string` | Estado previo de la versión (`"submitted"`). |
| `resulting_status` | `string` | Nuevo estado de la versión (`"approved"` o `"draft"`). |
| `reviewed_at` | `string` | Marca temporal ISO-8601 en UTC del registro de la revisión. |

### Ejemplos de respuesta

**Cuando `decision` es `"approved"` (`submitted` -> `approved`):**

```json
{
  "review_id": "550e8400-e29b-41d4-a716-446655440010",
  "version_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "reviewer_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "decision": "approved",
  "reason": "Atribución SPDX verificada, metadatos completos y archivo CSV íntegro.",
  "previous_status": "submitted",
  "resulting_status": "approved",
  "reviewed_at": "2026-11-26T23:45:00Z"
}
```

**Cuando `decision` es `"changes_requested"` (`submitted` -> `draft`):**

```json
{
  "review_id": "550e8400-e29b-41d4-a716-446655440011",
  "version_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "reviewer_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "decision": "changes_requested",
  "reason": "El identificador de la estación no coincide con el catálogo oficial y falta describir las variables medidas en el CSV.",
  "previous_status": "submitted",
  "resulting_status": "draft",
  "reviewed_at": "2026-11-26T23:47:00Z"
}
```

---

## 5. Efecto sobre las transiciones de estado

| Decisión | Estado origen | Estado destino | Efecto operativo |
| :--- | :--- | :--- | :--- |
| `approved` | `submitted` | `approved` | Habilita la versión para que un `org_admin` ejecute la publicación (`approved` -> `published`). |
| `changes_requested` | `submitted` | `draft` | Devuelve la versión a edición para que el autor incorpore observaciones y vuelva a enviarla a revisión. |

---

## 6. Errores del contrato

Todas las respuestas de error propagan la cabecera `X-Correlation-ID` y siguen
el sobre estándar de `apps/api` (`error`, `message`, `details`), equivalente a
`ErrorResponse` y a los metadatos de transición de
`docs/library-version-transitions.md`:

| Código HTTP | Código interno (`details.code`) | Causa |
| :--- | :--- | :--- |
| `401 Unauthorized` | `UNAUTHENTICATED` | Solicitud sin sesión autenticada o con token inválido/expirado. |
| `403 Forbidden` | `FORBIDDEN_REVIEWER_ROLE` | El usuario pertenece como miembro activo a la organización propietaria, pero no tiene rol `reviewer` ni `org_admin`, o intenta revisar su propia versión. |
| `404 Not Found` | `LIBRARY_VERSION_NOT_FOUND` | La versión `version_id` no existe o pertenece a otra organización a la que el usuario no tiene acceso (evita enumeración de UUIDs entre organizaciones). |
| `409 Conflict` | `INVALID_VERSION_TRANSITION` | La versión no está en estado `submitted` (por ejemplo, está en `draft`, `approved`, `published` o `withdrawn`, o ya fue revisada concurrentemente). |
| `422 Unprocessable Entity` | `VALIDATION_ERROR` | `version_id` inválido, `decision` fuera de catálogo, `reason` vacío/excede `1000` caracteres o presencia de campos no permitidos (como `reviewer_id`). |

Ejemplo de error por estado incompatible (`409 Conflict`):

```json
{
  "error": "Conflict",
  "message": "Transición de estado no permitida: solo se pueden revisar versiones en estado 'submitted'.",
  "details": {
    "code": "INVALID_VERSION_TRANSITION",
    "current_status": "draft",
    "target_status": "approved"
  }
}
```
