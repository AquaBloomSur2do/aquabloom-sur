# Recorrido web de revisión de biblioteca (S3-21)

## Alcance

Este esquema describe el recorrido para enviar una versión de biblioteca a
revisión, esperar una decisión y resolver una solicitud. Es una propuesta de
interfaz; no agrega rutas ni conecta una API. La pantalla existente
`/datasets/review` continúa dedicada a datasets.

Los estados y transiciones siguen la [matriz de versiones de biblioteca](./library-version-transitions.md):
`draft` → `submitted` → `approved` o regreso a `draft` con cambios solicitados.
La aprobación no publica automáticamente la versión.

## Mapa del recorrido

```text
AUTOR
Ficha del recurso
    └── Seleccionar versión draft
          └── Revisar metadatos y archivo
                └── Enviar a revisión
                      └── Estado submitted: esperar decisión
                            ├── Aprobada → mostrar aprobación y esperar publicación
                            └── Cambios solicitados → volver a editar draft

REVISOR
Bandeja de solicitudes
    ├── Con solicitudes → abrir una versión → aprobar o solicitar cambios
    └── Sin solicitudes → mostrar estado vacío, sin filas ficticias
```

## Esquema de pantallas

### 1. Seleccionar versión y preparar envío

```text
┌─────────────────────────────────────────────────────────────┐
│ Biblioteca / Recurso: Guía del Lago Azul                    │
│ Enviar una versión a revisión                               │
│                                                             │
│ Versión                                                     │
│ [ Selecciona una versión draft                         ▾ ]  │
│                                                             │
│ Versión 1.2.0 · Borrador                                    │
│ Autor: Equipo de monitoreo   Licencia: CC-BY-4.0            │
│ Lago: Lago Azul             Archivo: Validado               │
│                                                             │
│ [Volver al recurso]                    [Enviar a revisión]  │
└─────────────────────────────────────────────────────────────┘
```

- El selector lista las versiones `draft` del recurso; cada opción incluye
  número de versión y estado.
- El resumen muestra autor, licencia, lago y resultado de la comprobación del
  archivo antes de enviar.
- Si no hay versiones elegibles, se reemplaza el selector por el estado vacío
  **“No hay versiones en borrador disponibles”** y se ofrece volver al recurso.
- El envío se habilita solo cuando existe una versión seleccionada y satisface
  los requisitos de metadatos y archivo del proceso de revisión.

### 2. Envío y espera de decisión

Al activar **Enviar a revisión**, se bloquea el botón mientras se procesa la
solicitud. Si tiene éxito, la versión pasa a `submitted` y la pantalla muestra:

```text
┌─────────────────────────────────────────────────────────────┐
│ Solicitud enviada                                           │
│ Guía del Lago Azul · versión 1.2.0                           │
│ Estado: EN REVISIÓN                                         │
│                                                             │
│ La versión quedó bloqueada para edición mientras se revisa. │
│ Consulta el estado desde el seguimiento de la versión.       │
│                                                             │
│ [Volver al recurso]                                         │
└─────────────────────────────────────────────────────────────┘
```

La vista de espera mantiene el estado `submitted`, muestra la fecha de envío y
no ofrece otro botón para enviar la misma versión. Si la carga falla, conserva
la selección y muestra un error con una acción **Reintentar**.

### 3. Bandeja de solicitudes del revisor

Con solicitudes, la bandeja muestra recurso, versión, autor, lago y fecha de
envío; cada fila permite abrir el detalle de revisión.

```text
┌─────────────────────────────────────────────────────────────┐
│ Solicitudes de revisión                                     │
│ [Pendientes] [Resueltas]                                    │
│                                                             │
│ Recurso              Versión    Autor       Enviado    Ver  │
│ Guía del Lago Azul   1.2.0      Equipo A    26 nov.    [›]  │
└─────────────────────────────────────────────────────────────┘
```

Si la persona no tiene solicitudes pendientes, no se muestran filas de
ejemplo ni un panel en blanco:

```text
┌─────────────────────────────────────────────────────────────┐
│ Solicitudes de revisión                                     │
│                                                             │
│             No tienes solicitudes pendientes                │
│       Cuando se envíe una versión, aparecerá aquí.            │
│                                                             │
│                         [Actualizar]                        │
└─────────────────────────────────────────────────────────────┘
```

La bandeja distingue el estado vacío de carga y del error de consulta. Si no
hay solicitudes resueltas, la pestaña **Resueltas** muestra su propio mensaje
vacío sin afectar la bandeja pendiente.

### 4. Detalle y decisión

```text
┌─────────────────────────────────────────────────────────────┐
│ ← Solicitudes de revisión                                   │
│ Guía del Lago Azul · versión 1.2.0 · EN REVISIÓN            │
│ Autor: Equipo de monitoreo · Lago: Lago Azul                │
│ Licencia: CC-BY-4.0 · Archivo: Validado                     │
│                                                             │
│ [Metadatos y archivo de la versión]                          │
│                                                             │
│ Comentario de revisión                                       │
│ [Observaciones para el autor...                         ]   │
│                                                             │
│ [Solicitar cambios]                    [Aprobar versión]    │
└─────────────────────────────────────────────────────────────┘
```

- **Aprobar versión** cambia el estado de `submitted` a `approved`; se muestra
  una confirmación y la siguiente acción queda fuera de esta revisión:
  publicación por el rol autorizado.
- **Solicitar cambios** requiere un comentario no vacío, vuelve la versión a
  `draft` y muestra las observaciones para el autor.
- Mientras se guarda una decisión se deshabilitan ambas acciones. Un error
  conserva el comentario y permite reintentar; un éxito muestra la decisión y
  quién la registró.

## Reglas comunes de interacción

- Mostrar estados con texto además del color: **Borrador**, **En revisión** y
  **Aprobada**. Cuando se soliciten cambios, explicar que la versión volvió a
  **Borrador** e incluir las observaciones, sin inventar un estado persistido
  adicional.
- No confundir aprobación con publicación ni presentar una versión aprobada
  como disponible en el catálogo.
- Solo los roles autorizados por la matriz de transiciones pueden acceder a la
  bandeja y registrar decisiones.
- El usuario debe poder volver a la ficha del recurso sin perder el contexto
  del elemento seleccionado.
- Los estados de carga se anuncian con `role="status"` y los errores con
  `role="alert"`; los controles tienen etiquetas visibles y operables por
  teclado.
- En pantallas estrechas, la tabla de solicitudes se convierte en tarjetas con
  los mismos datos y acciones.

## Fuera de alcance

No se define aquí el contrato de endpoints ni se implementan la selección, el
envío o la decisión en la aplicación. La revisión de datasets y su publicación
continúan siendo un flujo separado.
