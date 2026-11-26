# Matriz de transiciones permitidas — Versión de biblioteca (S3-05)

**Ticket:** AQU-429 (`S3-05`)  
**Contexto:** Sprint 3 · Semana 1 — Contratos y base de cierre.  
Define el ciclo de vida, los roles autorizados y las transiciones válidas e inválidas para una versión de recurso científico en la biblioteca de AquaBloom Sur.

---

## 1. Estados de una versión de biblioteca

| Estado | Código | Descripción |
| :--- | :--- | :--- |
| **Borrador** | `draft` | Versión recién creada o en edición; visible solo dentro de la organización autora. |
| **En revisión** | `submitted` | Versión enviada a revisión científica/editorial; queda bloqueada para edición directa. |
| **Aprobada** | `approved` | Versión revisada y aprobada; lista para publicarse. |
| **Publicada** | `published` | Versión oficial disponible en el catálogo autorizado de la biblioteca. |
| **Retirada** | `withdrawn` | Versión dada de baja (desde borrador, revisión o publicada); no puede volver a publicarse directamente. |

---

## 2. Roles considerados

- **Autor / Investigador (`author`):** miembro activo de la organización propietaria del recurso que crea y prepara la versión.
- **Revisor (`reviewer`):** usuario con permiso de revisión encargado de evaluar una versión enviada (`S3-11`, `S3-35`, `S3-36`).
- **Administrador de organización / Publicador (`org_admin`):** responsable con permiso de publicación y retiro dentro de la organización (`S3-53`, `S3-70`).

---

## 3. Matriz de transiciones permitidas

| Acción | Estado origen | Estado destino | Roles autorizados | Regla / Condición mínima |
| :--- | :--- | :--- | :--- | :--- |
| **Crear** | *(ninguno)* | `draft` | `author`, `org_admin` | El usuario pertenece a la organización propietaria del recurso (`S3-30`, `S3-31`). |
| **Enviar a revisión** | `draft` | `submitted` | `author`, `org_admin` | La versión cuenta con metadatos mínimos, atribución y archivo válido (`S3-06`, `S3-07`, `S3-35`). |
| **Aprobar revisión** | `submitted` | `approved` | `reviewer`, `org_admin` | Decisión positiva registrada en auditoría (`S3-36`, `S3-68`). |
| **Solicitar cambios** | `submitted` | `draft` | `reviewer`, `org_admin` | Devuelve la versión a borrador con observaciones de revisión (`S3-36`). |
| **Publicar** | `approved` | `published` | `org_admin` | Requiere aprobación previa vigente y permiso de publicación en la organización (`S3-53`, `S3-70`). |
| **Retirar (previo a publicar)** | `draft`, `submitted`, `approved` | `withdrawn` | `author`, `org_admin` | Cancela la versión antes de su publicación. |
| **Retirar (publicada)** | `published` | `withdrawn` | `org_admin` | Retira del catálogo activo conservando trazabilidad e historial (`S3-67`). |

---

## 4. Casos de transición rechazada

### Caso principal: Publicar directamente desde borrador (`draft` -> `published`)

- **Actor:** `author` u `org_admin` intenta publicar una versión que aún está en estado `draft` (sin haber pasado por `submitted` ni `approved`).
- **Resultado esperado:**
  - **Código HTTP:** `409 Conflict`
  - **Efecto:** la transición es rechazada y la versión permanece en estado `draft`.
  - **Respuesta de error esperada:**

    ```json
    {
      "detail": "Transición de estado no permitida: no se puede publicar una versión desde 'draft'; debe estar en estado 'approved'.",
      "code": "INVALID_VERSION_TRANSITION",
      "current_status": "draft",
      "target_status": "published"
    }
    ```

### Otros casos rechazados de referencia

- **Rol no autorizado (`403 Forbidden`):** un usuario con rol `author` intenta ejecutar **Publicar** (`approved` -> `published`) o **Retirar** una versión ya `published`.
- **Reapertura de versión retirada (`409 Conflict`):** cualquier intento de pasar desde `withdrawn` a `draft` o `published` se rechaza; se debe crear una nueva versión (`S3-31`).


