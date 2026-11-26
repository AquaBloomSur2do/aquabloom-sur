# Formato de atribución de la biblioteca (S3-06)

**Ticket:** AQU-430 (`S3-06`)  
**Contexto:** Sprint 3 · Semana 1 — Contratos y base de cierre.

Este contrato define cómo identificar al autor, la licencia, la versión y la
fuente de un recurso de biblioteca. Se aplica a la atribución de cada versión
del recurso y sirve como base para el contrato mínimo y la persistencia que se
implementarán en tareas posteriores.

## Contrato

`attribution` es un objeto y debe incluir las cuatro propiedades siguientes.
La propiedad `license` es obligatoria aunque su valor pueda ser `null`.

| Propiedad | Tipo | Regla |
| :--- | :--- | :--- |
| `author` | objeto | Requiere `status` (`known` o `unknown`) y `name`. Con `known`, `name` es texto no vacío; con `unknown`, `name` es `null`. `orcid` es opcional y solo se informa si se conoce. |
| `license` | objeto o `null` | `null` significa que no se declaró una licencia; no implica dominio público ni concede permisos de reutilización. Si existe, requiere `spdx_id`; `url` es opcional. |
| `version` | string | Versión del recurso en formato SemVer `MAJOR.MINOR.PATCH`, opcionalmente con sufijo prerelease; por ejemplo, `1.2.0`. |
| `source` | objeto | Requiere `name`, no vacío. `url` puede ser una URL, DOI resoluble o `null` si la fuente no tiene localizador público. |

Omitir `author`, `license`, `version` o `source` es un error de contrato. En
particular, un autor desconocido se representa explícitamente en `author`;
una licencia ausente se representa con `"license": null`. No se debe usar el
valor de una propiedad para inferir el estado de la otra.

## Ejemplo con autor y licencia conocidos

```json
{
  "attribution": {
    "author": {
      "status": "known",
      "name": "María Pérez",
      "orcid": "0000-0002-1825-0097"
    },
    "license": {
      "spdx_id": "CC-BY-4.0",
      "url": "https://creativecommons.org/licenses/by/4.0/"
    },
    "version": "1.2.0",
    "source": {
      "name": "Repositorio de datos del Lago Azul",
      "url": "https://example.org/datasets/lago-azul"
    }
  }
}
```

Cita legible: **María Pérez, versión 1.2.0, Repositorio de datos del Lago
Azul, licencia CC-BY-4.0.**

## Ejemplo con autor desconocido y licencia no declarada

```json
{
  "attribution": {
    "author": {
      "status": "unknown",
      "name": null
    },
    "license": null,
    "version": "1.0.0",
    "source": {
      "name": "Importación histórica de biblioteca",
      "url": null
    }
  }
}
```

La interfaz puede mostrar **Autor desconocido** y **Licencia no declarada**.
No debe ocultar ambos datos ni sustituir la licencia ausente por una licencia
abierta por defecto.

## Reglas para validación y presentación

- `author.status` solo admite `known` o `unknown`.
- Si `author.status` es `known`, `author.name` debe contener un nombre no vacío.
- Si `author.status` es `unknown`, `author.name` debe ser `null`; no inventar ni
  inferir un autor a partir de la fuente.
- `license` debe ser `null` o incluir un identificador SPDX válido. Cuando se
  proporcione `url`, debe apuntar al texto de esa licencia.
- `source.name` identifica de dónde proviene el recurso; `source.url` permite
  rastrearlo cuando existe un localizador.
- La cita visible debe conservar autor, versión y fuente. Debe mostrar la
  licencia cuando está declarada y señalar expresamente cuando no lo está.
- La atribución describe procedencia y condiciones declaradas; no reemplaza la
  verificación de derechos de uso del recurso.
