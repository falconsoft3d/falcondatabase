---
title: "Tutorial: the REST API with curl and fetch"
date: 2026-09-19
category: tutorial
summary: Use falcondatabase from any language. Every endpoint, header and filter explained with curl and fetch examples.
tags: api, rest, curl
---
The JavaScript SDK is just a thin layer over a plain REST API. If you work in Python, PHP, Go, a mobile app or a shell script, this is all you need.

## Base URL and headers

```
%BASE_URL%/api/v1/PROJECT_REF
```

Every request sends the **apikey** header. Requests made on behalf of a signed-in user also send their token:

```
apikey: ANON_KEY
Authorization: Bearer USER_TOKEN
```

The **service key** gives full access and ignores access rules. Keep it on your servers.

## List rows

```bash
curl "%BASE_URL%/api/v1/PROJECT_REF/tables/products?price=gte.10&order=price.desc&limit=20" \
  -H "apikey: ANON_KEY"
```

Filters use the form `column=operator.value`:

| Example | Meaning |
|---|---|
| `price=gte.10` | price ≥ 10 |
| `name=ilike.%25coffee%25` | name contains "coffee" (`%25` is `%` URL-encoded) |
| `stock=is.null` | stock is NULL |
| `category=in.(drinks,desserts)` | category is one of the list |
| `active=eq.true` | exact match (`active=true` works too) |

Other parameters: `select=id,name`, `order=price.desc,name.asc`, `limit` (default 100, maximum 1000) and `offset`.

The response always has the same shape:

```json
{"data": [ ... ], "count": 42}
```

## Insert

```bash
curl -X POST "%BASE_URL%/api/v1/PROJECT_REF/tables/products" \
  -H "apikey: SERVICE_KEY" -H "Content-Type: application/json" \
  -d '{"name": "Tea", "price": 6.9}'
```

Send a JSON **list** to insert several rows in one transaction: if one fails, none is saved. The answer is `201` with the created row(s), including `id` and `created_at`.

## Get, update and delete one row

```bash
curl "%BASE_URL%/api/v1/PROJECT_REF/tables/products/7" -H "apikey: ANON_KEY"

curl -X PATCH "%BASE_URL%/api/v1/PROJECT_REF/tables/products/7" \
  -H "apikey: SERVICE_KEY" -H "Content-Type: application/json" -d '{"price": 7.5}'

curl -X DELETE "%BASE_URL%/api/v1/PROJECT_REF/tables/products/7" -H "apikey: SERVICE_KEY"
```

## Users

| Method | Path | Body → result |
|---|---|---|
| POST | `/auth/signup` | `{"email", "password", "data"?}` → `{user, token, expires_in}` |
| POST | `/auth/login` | `{"email", "password"}` → `{user, token, expires_in}` |
| GET | `/auth/user` | current user (needs the token) |
| PATCH | `/auth/user` | `{"data": {...}}` merges profile data |

Tokens last 7 days by default.

## The same with fetch

```js
const BASE = "%BASE_URL%/api/v1/PROJECT_REF"
const headers = { apikey: "ANON_KEY", "Content-Type": "application/json" }

const res = await fetch(`${BASE}/tables/products?order=price.desc`, { headers })
const { data, count, error } = await res.json()
```

## Errors

Errors come back as JSON with an HTTP status: `{"error": "message"}`.

| Status | When |
|---|---|
| 400 | invalid filter, unknown column, value of the wrong type |
| 401 | missing or invalid key, or the table needs a signed-in user |
| 403 | private table, login disabled, sign up disabled |
| 404 | unknown project, table or row |
| 409 | email already registered |

Messages are in English or Spanish depending on the `Accept-Language` header.
