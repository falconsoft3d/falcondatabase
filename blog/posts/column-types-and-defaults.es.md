---
title: "Guía: tipos de columna, valores por defecto y restricciones"
date: 2026-10-13
category: guide
summary: Qué tipo elegir para cada columna, cómo funcionan los valores por defecto como now() y uuid(), y qué significan de verdad obligatorio y único.
tags: postgresql, esquema, tablas
---
Cada columna que creas en falcondatabase es una columna real de PostgreSQL. Elegir el tipo correcto te da validación gratis y hace que los filtros funcionen como esperas.

## Los diez tipos

| Tipo | PostgreSQL | Úsalo para | Valor JSON en la API |
|---|---|---|---|
| `text` | `text` | nombres, descripciones, cualquier texto | `"Café"` |
| `integer` | `integer` | conteos, cantidades (±2 mil millones) | `42` |
| `bigint` | `bigint` | contadores muy grandes, ids externos | `9007199254740` |
| `decimal` | `numeric` | dinero y valores exactos | `12.5` |
| `float` | `double precision` | medidas, coordenadas | `3.14159` |
| `boolean` | `boolean` | indicadores sí/no | `true` |
| `date` | `date` | cumpleaños, vencimientos | `"2026-10-13"` |
| `datetime` | `timestamp with time zone` | eventos, marcas de tiempo | `"2026-10-13T09:30:00Z"` |
| `json` | `jsonb` | datos flexibles: ajustes, etiquetas, objetos anidados | `{"tags": ["a"]}` |
| `uuid` | `uuid` | identificadores públicos que no se pueden adivinar | `"6f1c…"` |

> Usa `decimal` para precios: `float` no puede guardar 0.1 exactamente. La API devuelve los decimales como números JSON para que tu frontend pueda operar con ellos directamente.

## Columnas automáticas

Toda tabla empieza con:

- `id` — `bigint` generado automáticamente, la clave primaria que usa `/tables/<nombre>/<id>`.
- `created_at` — `datetime` con valor por defecto `now()`.
- `owner_id` — solo en tablas con la regla de acceso **Dueño**.

Son columnas del sistema: no se pueden eliminar y los clientes con la anon key no pueden escribirlas.

## Valores por defecto

Escribe un valor en el campo **Por defecto** al crear una columna. Se convierte al tipo de la columna, así que `0`, `true` o `pendiente` funcionan. Hay dos valores especiales:

| Valor | Tipos | Resultado |
|---|---|---|
| `now()` | `date`, `datetime` | fecha / hora actual al insertar |
| `uuid()` | `uuid` | un UUID aleatorio nuevo por fila |

El valor por defecto se aplica cuando la inserción no incluye la columna.

## Obligatorio y único

- **Obligatorio** agrega `NOT NULL`: las inserciones sin valor (y sin valor por defecto) fallan con un error claro.
- **Único** agrega una restricción `UNIQUE`: ideal para emails, slugs o SKU. Un duplicado devuelve `400` con el mensaje de PostgreSQL.

Agregar una columna **obligatoria** a una tabla que ya tiene filas necesita un valor por defecto; si no, PostgreSQL no puede rellenar las filas existentes.

## Cambiar la estructura después

Desde la pestaña **Estructura** de la tabla puedes agregar y quitar columnas. Quitar una columna borra sus datos. Para cambiar un tipo, agrega una columna nueva, copia los datos con la API o con SQL y elimina la anterior.

## Filtrar según el tipo

| Tipo | Filtros útiles |
|---|---|
| text | `eq`, `ilike.%25palabra%25`, `in.(a,b)` |
| números, fechas | `gt`, `gte`, `lt`, `lte` |
| boolean | `eq.true`, `is.false` |
| cualquiera | `is.null` |
| json | `like` / `ilike` sobre su representación en texto |

Por ejemplo, los pedidos de octubre: `created_at=gte.2026-10-01&created_at=lt.2026-11-01`.
