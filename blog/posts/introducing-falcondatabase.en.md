---
title: Introducing falcondatabase
date: 2026-09-01
category: news
summary: A simple, self-hosted alternative to Firebase and Supabase built with Django and PostgreSQL.
tags: announcement, postgresql, django
---
Every app needs the same boring pieces: a database, an API to reach it, and a way for users to sign in. **falcondatabase** gives you all three in a few clicks, on your own server, with an interface that feels like GitHub.

## Why another backend?

Firebase and Supabase are great, but sometimes you want something you can read end to end, run on a small VPS and adapt to your needs. falcondatabase is a regular Django project backed by PostgreSQL:

- **Real tables.** Each table you create is a real PostgreSQL table, not a JSON blob. You can query it with SQL whenever you need to.
- **Isolated projects.** Every project lives in its own PostgreSQL schema, with its own API URL and keys.
- **Login included.** Turn on email and password authentication for the users of your app with one checkbox.
- **Access rules per table.** Public, public read, signed-in users only, per owner or private.
- **A REST API and a tiny SDK.** Query from React, Vue, Svelte or plain JavaScript without installing anything.

## What you get in the dashboard

| Tab | What it does |
|---|---|
| Overview | URL, keys and a quick start snippet |
| Tables | Create tables, edit rows, add or remove columns |
| Authentication | Enable login and manage your app's users |
| Analytics | Cookie-free web analytics for your websites |
| Storage | Buckets for images, documents and other files |
| Portal | Publish the project as a ready-made app for its users |
| API | Full reference with your real keys filled in |
| Settings | Rename, export, regenerate keys or delete the project |

Your account can also be protected with **two-step authentication**, and the whole interface is available in **English and Spanish**, in light and dark mode.

## A taste of the SDK

```js
import { createClient } from "%BASE_URL%/sdk/falcondb.js"

const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
const { data } = await db.from("products").select().gte("price", 10).order("price", { desc: true })
```

## Where to go next

Start with the tutorial **Your first project in 5 minutes**, then learn how to query your data from JavaScript. If you want to run your own instance, the Docker guide gets you from an empty server to HTTPS in a single script.

Questions or ideas? Write to the author at the contact address in the footer.
