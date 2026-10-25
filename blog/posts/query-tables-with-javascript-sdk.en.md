---
title: "Tutorial: query your tables with the JavaScript SDK"
date: 2026-09-12
category: tutorial
summary: Filter, sort, paginate and write data from any web page with falcondb.js, a single file with no dependencies.
tags: javascript, sdk, frontend
---
`falcondb.js` is a tiny ES module served by your own falcondatabase server. There is nothing to install and no build step: import it from a `<script type="module">` and start querying.

## Create the client

```html
<script type="module">
  import { createClient } from "%BASE_URL%/sdk/falcondb.js"

  const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
</script>
```

Use the **anon key** in the browser. It is public by design: what it can do is limited by the access rule of each table.

## Read rows

`db.from(table)` returns a query builder. Chain filters and `await` it:

```js
const { data, count, error } = await db.from("products")
  .select("id,name,price")      // optional: only these columns
  .gte("price", 10)             // price >= 10
  .ilike("name", "%coffee%")    // case-insensitive pattern
  .order("price", { desc: true })
  .limit(20)
```

| Method | SQL |
|---|---|
| `eq(col, v)` / `neq(col, v)` | `=` / `<>` |
| `gt`, `gte`, `lt`, `lte` | `>`, `>=`, `<`, `<=` |
| `like(col, p)` / `ilike(col, p)` | `LIKE` / `ILIKE` (`%` is the wildcard) |
| `is(col, "null")` | `IS NULL` (also `true` / `false`) |
| `in(col, ["a", "b"])` | `IN ('a', 'b')` |

`count` is the total number of matching rows, perfect for pagination.

## Paginate

```js
const page = 2, size = 20
const { data, count } = await db.from("products")
  .order("id")
  .range((page - 1) * size, page * size - 1)

const pages = Math.ceil(count / size)
```

`range(from, to)` is a shortcut for `offset(from).limit(to - from + 1)`.

## Get a single row

```js
const { data: product } = await db.from("products").get(7)          // by id
const { data: first } = await db.from("products").eq("name", "Tea").single()  // first match or null
```

## Write data

```js
await db.from("products").insert({ name: "Croissant", price: 2.2 })
await db.from("products").insert([{ name: "A" }, { name: "B" }])  // several rows, all or nothing
await db.from("products").update(7, { price: 3 })
await db.from("products").delete(7)
```

Writes respect the table's access rule. With **Public read**, for example, inserting requires a signed-in user (see the to-do app tutorial).

## Handle errors

The SDK never throws for API errors. Every call resolves to `{ data, error }`:

```js
const { data, error } = await db.from("products").insert({ price: "cheap" })
if (error) {
  console.error(error.status, error.message)   // 400 invalid input syntax for type numeric...
}
```

Error messages follow the browser language (English or Spanish).

## Discover the schema

```js
const { data } = await db.schema()
console.log(data.tables)   // tables visible with your key, with their columns and types
```

That's all you need for most apps. Next: build a to-do app where each user only sees their own tasks.
