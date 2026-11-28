# Contrato mínimo de recurso de biblioteca (S3-07)

**Objetivo:** definir los metadatos mínimos de un recurso de biblioteca sin
confundir su publicación con la creación o publicación de un dataset.

## Representación del recurso

El contrato mínimo requiere todos los campos de la tabla. Si un dato no aplica
o se desconoce, se representa explícitamente como se indica; no se omiten
propiedades requeridas.

| Campo | Tipo | Regla |
| :--- | :--- | :--- |
| `title` | string | Obligatorio, no vacío después de quitar espacios, máximo 200 caracteres. |
| `author` | objeto | Obligatorio. Usa `status` (`known` o `unknown`) y `name` según el [formato de atribución](./library-attribution-format.md); `orcid` es opcional. |
| `type` | string | Obligatorio. Identificador estable en minúsculas, entre 1 y 64 caracteres; ejemplos: `dataset`, `model`, `document`. Los ejemplos no forman una lista cerrada. |
| `license` | objeto o `null` | Obligatorio. Si existe, requiere `spdx_id` y admite `url`, según el [formato de atribución](./library-attribution-format.md). `null` significa que no se declaró licencia; no concede permisos de reutilización. |
| `lake_id` | UUID o `null` | Obligatorio. Identifica el lago asociado; `null` indica que el recurso no corresponde a un único lago. |
| `visibility` | string | Obligatorio. Admite `private` o `public`. `private` no aparece en el catálogo público; `public` permite descubrir el recurso en él. |

## Ejemplo

```json
{
  "title": "Guía de monitoreo del Lago Villarrica",
  "author": {
    "status": "known",
    "name": "Equipo de monitoreo"
  },
  "type": "document",
  "license": {
    "spdx_id": "CC-BY-4.0",
    "url": "https://creativecommons.org/licenses/by/4.0/"
  },
  "lake_id": "44444444-4444-4444-8444-444444444444",
  "visibility": "private"
}
```

## Regla de publicación e independencia de Dataset

Publicar un recurso de biblioteca solo cambia su disponibilidad dentro de la
biblioteca. No debe crear, publicar, actualizar ni eliminar datasets,
versiones, membresías o manifiestos; tampoco debe invocar el flujo de
publicación de versiones de Dataset. La regla se mantiene aunque
`type` tenga el valor `dataset`: publicar el recurso no publica ni modifica
ningún dataset.

Este contrato define la regla para el flujo futuro de biblioteca. Actualmente
no hay un endpoint de biblioteca en `apps/api`; por tanto, esta tarea no
implementa ni valida en runtime una operación de publicación.
