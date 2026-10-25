---
title: "Tutorial: your first project in 5 minutes"
date: 2026-09-05
category: tutorial
summary: Create an account, a project and a table, add some rows and read them through the API.
tags: getting-started, dashboard
---
In this tutorial you will go from zero to a working API: an account, a project, a `products` table with data, and a first request from the terminal.

## 1. Create your account

Open %BASE_URL%/signup/ and choose a **username** (letters, numbers and hyphens), your email and a password. Your username becomes part of your project URLs, like `/your-name/my-shop/`.

> If sign up is disabled on this server, ask the administrator to create the account for you.

## 2. Create a project

From the dashboard click **New project**, give it a name such as `My shop` and press **Create project**. falcondatabase creates:

- a PostgreSQL schema just for this project,
- an API URL: `%BASE_URL%/api/v1/<ref>`,
- an **anon key** (safe for the browser) and a **service key** (secret, server only).

You will find all three in the **Connection** box of the project overview.

## 3. Create a table

Go to the **Tables** tab and click **New table**:

1. Name: `products`.
2. Columns:
    - `name` — type `text`, mark **Req.** (NOT NULL),
    - `price` — type `decimal`,
    - `stock` — type `integer`, default `0`,
    - `active` — type `boolean`, default `true`.
3. API access: leave **Public read** (anyone reads, only signed-in users write).

Every table automatically gets an `id` (auto-increment) and `created_at` (set to `now()`).

## 4. Add some rows

Open the table and expand **Insert row**. Add a few products. You can sort by any column by clicking its header, edit a row with the pencil icon and delete it with the trash icon.

## 5. Read the data through the API

Copy your project **ref** and **anon key** and try:

```bash
curl "%BASE_URL%/api/v1/PROJECT_REF/tables/products?order=price.desc" \
  -H "apikey: ANON_KEY"
```

The answer looks like this:

```json
{
  "data": [
    {"id": 2, "created_at": "2026-09-05T10:00:00Z", "name": "Coffee", "price": 12.5, "stock": 40, "active": true}
  ],
  "count": 1
}
```

`count` is the total number of matching rows, independently of pagination.

## What's next

- Query the table from a web page with the JavaScript SDK.
- Learn the difference between the five access rules before you go public.
- The **API** tab of each table shows ready-to-copy examples with your real keys.
