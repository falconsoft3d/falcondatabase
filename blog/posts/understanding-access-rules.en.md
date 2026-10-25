---
title: "Guide: understanding access rules"
date: 2026-09-26
category: guide
summary: Public, public read, signed-in users, owner or private. Pick the right rule for each table before you go live.
tags: security, access-rules, auth
---
The **anon key** lives in your frontend, so anyone can read it. What protects your data is the **access rule** of each table. You choose it when you create the table and can change it any time from the table's **Structure** tab.

## The five rules

| Rule | Read | Write | Typical use |
|---|---|---|---|
| **Public** | anyone | anyone | prototypes, public guest books |
| **Public read** | anyone | signed-in users | catalogs, blog posts, comments |
| **Signed-in users** | signed-in users | signed-in users | internal tools, members-only content |
| **Owner** | only their rows | only their rows | to-do lists, notes, orders, profiles |
| **Private** | service key | service key | data only your backend touches |

"Signed-in users" are the users of *your app* (the **Authentication** tab of the project), not falcondatabase accounts. Their requests include `Authorization: Bearer <token>`.

The **service key** bypasses every rule. Use it in server code, cron jobs and admin scripts, never in a browser.

## How "Owner" works

When you choose **Owner**, falcondatabase adds an `owner_id` column to the table. Then:

1. On insert, `owner_id` is set automatically to the signed-in user. Whatever the client sends is ignored.
2. Reads only return rows where `owner_id` is the current user.
3. Updates and deletes only affect the user's own rows. Someone else's row behaves as if it didn't exist (`404`).

```js
await db.auth.signIn({ email, password })
await db.from("notes").insert({ text: "Buy milk" })   // owner_id is filled in for you
const { data } = await db.from("notes").select()       // only my notes
```

With the service key you see every row, including `owner_id`, which is handy for admin dashboards.

## What happens when access is denied

| Situation | Answer |
|---|---|
| Anonymous request to a table that needs a user | `401 You need to sign in for this operation.` |
| Any request with the anon key to a **Private** table | `404` (the table is hidden) |
| Expired or invalid token | `401 Invalid or expired token.` |

## System columns are protected

Clients using the anon key can't write `id`, `created_at` or `owner_id`. Those keys are silently removed from inserts and updates, so a user can't steal a row by changing its owner.

## A checklist before going live

- Start from **Public read** or stricter. Use **Public** only for data anyone may change.
- Store per-user data in **Owner** tables.
- Use **Private** plus the service key for anything sensitive.
- Turn off **Allow public sign up** in the Authentication tab if only you should create users.
- Regenerate the keys from **Settings** if the service key ever leaks.
