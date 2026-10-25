---
title: "Tutorial: consulta tus tablas con el SDK de JavaScript"
date: 2026-09-12
category: tutorial
summary: Filtra, ordena, pagina y escribe datos desde cualquier página web con falcondb.js, un único archivo sin dependencias.
tags: javascript, sdk, frontend
---
`falcondb.js` es un pequeño módulo ES que sirve tu propio servidor falcondatabase. No hay nada que instalar ni build: impórtalo desde un `<script type="module">` y empieza a consultar.

## Crea el cliente

```html
<script type="module">
  import { createClient } from "%BASE_URL%/sdk/falcondb.js"

  const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
</script>
```

Usa la **anon key** en el navegador. Es pública por diseño: lo que puede hacer lo limita la regla de acceso de cada tabla.

## Leer filas

`db.from(tabla)` devuelve un constructor de consultas. Encadena filtros y usa `await`:

```js
const { data, count, error } = await db.from("productos")
  .select("id,nombre,precio")     // opcional: solo estas columnas
  .gte("precio", 10)              // precio >= 10
  .ilike("nombre", "%cafe%")      // patrón sin distinguir mayúsculas
  .order("precio", { desc: true })
  .limit(20)
```

| Método | SQL |
|---|---|
| `eq(col, v)` / `neq(col, v)` | `=` / `<>` |
| `gt`, `gte`, `lt`, `lte` | `>`, `>=`, `<`, `<=` |
| `like(col, p)` / `ilike(col, p)` | `LIKE` / `ILIKE` (`%` es el comodín) |
| `is(col, "null")` | `IS NULL` (también `true` / `false`) |
| `in(col, ["a", "b"])` | `IN ('a', 'b')` |

`count` es el total de filas que cumplen el filtro, ideal para paginar.

## Paginar

```js
const pagina = 2, tamano = 20
const { data, count } = await db.from("productos")
  .order("id")
  .range((pagina - 1) * tamano, pagina * tamano - 1)

const paginas = Math.ceil(count / tamano)
```

`range(desde, hasta)` es un atajo de `offset(desde).limit(hasta - desde + 1)`.

## Obtener una sola fila

```js
const { data: producto } = await db.from("productos").get(7)                 // por id
const { data: primero } = await db.from("productos").eq("nombre", "Té").single()  // primera coincidencia o null
```

## Escribir datos

```js
await db.from("productos").insert({ nombre: "Croissant", precio: 2.2 })
await db.from("productos").insert([{ nombre: "A" }, { nombre: "B" }])  // varias filas, todas o ninguna
await db.from("productos").update(7, { precio: 3 })
await db.from("productos").delete(7)
```

Las escrituras respetan la regla de acceso de la tabla. Con **Lectura pública**, por ejemplo, insertar requiere un usuario con sesión (mira el tutorial de la app de tareas).

## Manejar errores

El SDK nunca lanza excepciones por errores de la API. Cada llamada devuelve `{ data, error }`:

```js
const { data, error } = await db.from("productos").insert({ precio: "barato" })
if (error) {
  console.error(error.status, error.message)   // 400 sintaxis de entrada no válida para tipo numeric...
}
```

Los mensajes de error siguen el idioma del navegador (español o inglés).

## Descubrir el esquema

```js
const { data } = await db.schema()
console.log(data.tables)   // tablas visibles con tu clave, con sus columnas y tipos
```

Con esto tienes lo necesario para la mayoría de apps. Siguiente paso: una app de tareas donde cada usuario solo ve las suyas.
