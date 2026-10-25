---
title: "Guide: column types, defaults and constraints"
date: 2026-10-13
category: guide
summary: Which type to choose for each column, how defaults like now() and uuid() work, and what required and unique really mean.
tags: postgresql, schema, tables
---
Every column you create in falcondatabase is a real PostgreSQL column. Picking the right type gives you validation for free and makes filters behave as you expect.

## The ten types

| Type | PostgreSQL | Use it for | JSON value in the API |
|---|---|---|---|
| `text` | `text` | names, descriptions, any string | `"Coffee"` |
| `integer` | `integer` | counts, quantities (±2 billion) | `42` |
| `bigint` | `bigint` | very large counters, external ids | `9007199254740` |
| `decimal` | `numeric` | money and exact values | `12.5` |
| `float` | `double precision` | measurements, coordinates | `3.14159` |
| `boolean` | `boolean` | yes/no flags | `true` |
| `date` | `date` | birthdays, due dates | `"2026-10-13"` |
| `datetime` | `timestamp with time zone` | events, timestamps | `"2026-10-13T09:30:00Z"` |
| `json` | `jsonb` | flexible data: settings, tags, nested objects | `{"tags": ["a"]}` |
| `uuid` | `uuid` | public identifiers that can't be guessed | `"6f1c…"` |

> Use `decimal` for prices: `float` can't store 0.1 exactly. The API returns decimals as JSON numbers so your frontend can do math with them directly.

## Automatic columns

Every table starts with:

- `id` — `bigint` generated automatically, the primary key used by `/tables/<name>/<id>`.
- `created_at` — `datetime` with default `now()`.
- `owner_id` — only on tables with the **Owner** access rule.

These are system columns: they can't be removed, and clients using the anon key can't write them.

## Defaults

Type a value in the **Default** field when creating a column. It is cast to the column type, so `0`, `true` or `pending` all work. Two special values are available:

| Default | Types | Result |
|---|---|---|
| `now()` | `date`, `datetime` | current date / time at insert |
| `uuid()` | `uuid` | a new random UUID per row |

A default applies when the insert doesn't include the column.

## Required and unique

- **Required** adds `NOT NULL`: inserts without a value (and without a default) fail with a clear error.
- **Unique** adds a `UNIQUE` constraint: perfect for emails, slugs or SKUs. A duplicate returns `400` with the PostgreSQL message.

Adding a **required** column to a table that already has rows needs a default value, otherwise PostgreSQL can't fill the existing rows.

## Changing the structure later

From the table's **Structure** tab you can add and remove columns. Removing a column deletes its data. To change a type, add a new column, copy the data with the API or SQL, and remove the old one.

## Filtering by type

| Type | Useful filters |
|---|---|
| text | `eq`, `ilike.%25word%25`, `in.(a,b)` |
| numbers, dates | `gt`, `gte`, `lt`, `lte` |
| boolean | `eq.true`, `is.false` |
| any | `is.null` |
| json | `like` / `ilike` on its text representation |

For example, orders from October: `created_at=gte.2026-10-01&created_at=lt.2026-11-01`.
