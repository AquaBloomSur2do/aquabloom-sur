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

### Caso A: Campo Opcional
- **Cambio compatible:** Agregar un campo opcional `is_active` (`boolean`, opcional / con valor por defecto `true`) en la respuesta o payload. Los clientes anteriores que no envían o no leen `is_active` siguen funcionando sin cambios.
- **Cambio de ruptura:** Hacer que `is_active` sea obligatorio (requerido sin defecto), cambiarlo a string o eliminarlo tras haber sido adoptado por los clientes.
- **Lista de control aplicada:**
  1. ¿Sigue siendo válido el contrato para consumidores que no envían/usan el campo nuevo?
  2. ¿Tiene valor por defecto o manejo seguro en consumidores existentes?
  3. Si es ruptura, ¿está versionado y anunciado con ventana de migración?

### Caso B: Código de Error
- **Cambio compatible:** Agregar un nuevo código de error específico (por ejemplo, un código de dominio/validación adicional manteniendo la estructura uniforme de error con `code`, `message`, `details` y `correlation_id`) sin modificar ni quitar los códigos de error ya documentados.
- **Cambio de ruptura:** Cambiar el código HTTP de un error ya existente (por ejemplo, pasar un error de `400`/`422` a `500` o a otro código distinto sin transición) o renombrar/eliminar un código de error que los clientes ya manejan.
- **Lista de control aplicada:**
  1. ¿Conserva el formato estándar de error y los códigos HTTP/identificadores previos intactos?
  2. ¿Los clientes existentes caen en un manejo seguro ante un nuevo código de error?
  3. Si se modifica o retira un error existente, ¿se documentó el periodo de transición y el versionado?
