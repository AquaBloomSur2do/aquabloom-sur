# Contrato de revisión de versiones de biblioteca (S3-11)

**Ticket:** `S3-11`  
**Contexto:** Sprint 3 · Semana 1 — Contratos y base de cierre.

Este contrato define la solicitud, la identificación del revisor, la decisión,
el motivo, los errores y los efectos de estado para revisar una versión
concreta de un recurso de biblioteca (`version_id`). Sirve como especificación
base antes de implementar la persistencia y los endpoints del dominio `library`.

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
- **Roles autorizados:** `reviewer` u `org_admin` dentro de la organización
  propietaria del recurso (alineado con `docs/library-version-transitions.md`).
- **Precondición de estado:** la versión objetivo (`version_id`) debe existir y
  encontrarse exactamente en estado `submitted`.

### Identificación del revisor

- El identificador del revisor (`reviewer_id`) se obtiene **exclusivamente** de
  la sesión autenticada en el servidor.
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
| `reason` | `string` | Sí | Texto no vacío (`min_length=1`, sin solo espacios) que fundamenta la aprobación o detalla las correcciones requeridas. |

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
  "reason": "Falta declarar la URL de la licencia SPDX y corregir el identificador de la estación."
}
```

---

## 4. Respuesta exitosa (`201 Created`)

Al registrarse la revisión, el servicio persiste la decisión asociada a
`version_id` y aplica la transición de estado correspondiente definida en
`docs/library-version-transitions.md`:

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `review_id` | `UUID` | Identificador único del registro de revisión generado. |
| `version_id` | `UUID` | Identificador de la versión de biblioteca evaluada. |
| `reviewer_id` | `UUID` | Identificador del usuario revisor derivado de la sesión autenticada. |
| `decision` | `string` | `"approved"` o `"changes_requested"`. |
| `reason` | `string` | Motivo registrado por el revisor. |
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
  "reason": "Falta declarar la URL de la licencia SPDX y corregir el identificador de la estación.",
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

| Código HTTP | Código interno | Causa |
| :--- | :--- | :--- |
| `401 Unauthorized` | `UNAUTHENTICATED` | Solicitud sin sesión autenticada o con token inválido/expirado. |
| `403 Forbidden` | `FORBIDDEN_REVIEWER_ROLE` | El usuario autenticado no pertenece a la organización propietaria o no tiene rol `reviewer` ni `org_admin`. |
| `404 Not Found` | `LIBRARY_VERSION_NOT_FOUND` | La versión `version_id` no existe o no es accesible para la organización del usuario. |
| `409 Conflict` | `INVALID_VERSION_TRANSITION` | La versión no está en estado `submitted` (por ejemplo, está en `draft`, `approved`, `published` o `withdrawn`). |
| `422 Unprocessable Entity` | `VALIDATION_ERROR` | `version_id` inválido, `decision` fuera de catálogo, `reason` vacío o presencia de campos no permitidos (como `reviewer_id`). |

Ejemplo de error por estado incompatible (`409 Conflict`):

```json
{
  "detail": "Transición de estado no permitida: solo se pueden revisar versiones en estado 'submitted'.",
  "code": "INVALID_VERSION_TRANSITION",
  "current_status": "draft",
  "target_status": "approved"
}
```
