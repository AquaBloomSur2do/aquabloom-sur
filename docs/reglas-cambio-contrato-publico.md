# Reglas de Cambio del Contrato Público (S3-13 / AQU-433)

## 1. Principio General
- **Preferencia aditiva:** Los cambios en contratos públicos (JSON / OpenAPI / esquemas de intercambio) deben ser compatibles hacia atrás siempre que sea posible.
- **Trazabilidad y transición:** Cualquier cambio de ruptura (*breaking change*) requiere versión/identificador explícito (`RN-18`), validación estricta de contratos (`RN-16`) y un periodo de transición coordinado sin romper clientes existentes (`RF-75`, `RF-76`).

## 2. Lista de Control: Cambios Compatibles vs. Rupturas

### Cambios Compatibles (Hacia Atrás)
- [ ] Agregar un campo opcional en request o response con valor por defecto o `nullable` sin alterar campos existentes.
- [ ] Agregar un nuevo valor permitido o nuevo código de error de dominio manteniendo intactos los códigos y formatos ya publicados.
- [ ] Agregar un nuevo endpoint o parámetro de consulta opcional sin cambiar el comportamiento de los existentes.
- [ ] Relajar una restricción de entrada (por ejemplo, permitir un valor adicional válido).

### Cambios de Ruptura (*Breaking Changes*)
- [ ] Eliminar o renombrar un campo existente en request o response.
- [ ] Convertir un campo opcional en obligatorio (sin valor por defecto) o cambiar su tipo de dato / formato incompatible.
- [ ] Eliminar, renombrar o cambiar el código HTTP / significado de un código de error existente.
- [ ] Endurecer validaciones de forma que payloads antes válidos ahora sean rechazados sin aviso/transición.

## 3. Aplicación del Criterio a Casos Concretos

> **Nota sobre request/response y formato de error:** En campos opcionales, conviene distinguir entre *request* (agregar un campo opcional/con defecto es compatible; hacerlo obligatorio sin defecto es ruptura) y *response* (agregar un campo nuevo es compatible si los consumidores ignoran campos desconocidos, pero volver opcional/`nullable` un campo antes siempre presente es ruptura para clientes estrictos). En errores, la estructura uniforme de contrato se expresa como `{code, message, details, correlation_id}`, teniendo en cuenta que el runtime de los servicios puede devolver `{error, message, details}` o `{detail}` con la cabecera `X-Correlation-ID`.

### Caso A: Campo Opcional
- **Cambio compatible:** Agregar un campo opcional `is_active` (`boolean`, opcional / con valor por defecto `true`) en el payload o respuesta. Los clientes anteriores que no envían o no leen `is_active` siguen funcionando sin cambios.
- **Cambio de ruptura:** Hacer que `is_active` sea obligatorio en *request* (requerido sin defecto), volver opcional/`nullable` en *response* un campo que antes venía siempre garantizado, cambiar su tipo a `string` o eliminarlo tras haber sido adoptado por los clientes.
- **Lista de control aplicada (escenario compatible — agregar `is_active` opcional):**
  1. ¿Sigue siendo válido el contrato para consumidores que no envían/usan el campo nuevo? **Sí.**
  2. ¿Tiene valor por defecto o manejo seguro en consumidores existentes? **Sí** (`true` por defecto / ignorado por clientes previos).
  3. Si es ruptura, ¿está versionado y anunciado con ventana de migración? **No aplica** (no es un cambio de ruptura).
  - **Dictamen:** **Compatible hacia atrás.**
- **Lista de control aplicada (escenario de ruptura — hacer `is_active` obligatorio sin defecto o eliminarlo):**
  1. ¿Sigue siendo válido el contrato para consumidores que no envían/usan el campo nuevo? **No.**
  2. ¿Tiene valor por defecto o manejo seguro en consumidores existentes? **No.**
  3. Si es ruptura, ¿está versionado y anunciado con ventana de migración? **No** (requiere versionado/anuncio previo; si no existe ventana de migración, se rechaza o se trata como ruptura).
  - **Dictamen:** **Cambio de ruptura (*breaking change*).**

### Caso B: Código de Error
- **Cambio compatible:** Agregar un nuevo código de error específico —por ejemplo, `DATASET_VERSION_NOT_PUBLISHED` con estado HTTP `409 Conflict` al intentar entrenar o publicar una versión de dataset aún en borrador— manteniendo intacta la estructura uniforme de error (`code`, `message`, `details`, `correlation_id`) y sin modificar ni retirar los códigos de error ya documentados.
- **Cambio de ruptura:** Cambiar el código HTTP de un error ya existente (por ejemplo, pasar un error de `422` a `400` o `500` sin transición) o renombrar/eliminar un código de error que los clientes ya manejan.
- **Lista de control aplicada (escenario compatible — agregar `DATASET_VERSION_NOT_PUBLISHED` con `409 Conflict`):**
  1. ¿Conserva el formato estándar de error y los códigos HTTP/identificadores previos intactos? **Sí.**
  2. ¿Los clientes existentes caen en un manejo seguro ante un nuevo código de error? **Sí** (por código HTTP genérico `409` o mensaje/fallback estándar).
  3. Si se modifica o retira un error existente, ¿se documentó el periodo de transición y el versionado? **No aplica** (no se modifica ni retira ningún error existente).
  - **Dictamen:** **Compatible hacia atrás.**
- **Lista de control aplicada (escenario de ruptura — cambiar un error de `422` a `400` o renombrar un código existente):**
  1. ¿Conserva el formato estándar de error y los códigos HTTP/identificadores previos intactos? **No.**
  2. ¿Los clientes existentes caen en un manejo seguro ante un nuevo código de error? **No** (clientes que ramifican por código de error o estado HTTP previo ven alterado su comportamiento esperado).
  3. Si se modifica o retira un error existente, ¿se documentó el periodo de transición y el versionado? **No** (sin ventana de transición ni versionado acordado, no puede aplicarse).
  - **Dictamen:** **Cambio de ruptura (*breaking change*).**

