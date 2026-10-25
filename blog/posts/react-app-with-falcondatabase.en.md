---
title: "Tutorial: use falcondatabase from React"
date: 2026-10-08
category: tutorial
summary: A shared client, a small useQuery hook and an auth-aware component for React or Next.js apps.
tags: react, javascript, frontend
---
The SDK is framework agnostic, so it fits naturally in React. In this tutorial we'll create one shared client, a reusable hook, and a component that reacts to sign in and sign out.

## 1. Add the SDK to your project

Download the module once into your source tree, so your bundler can import it:

```bash
curl -o src/falcondb.js %BASE_URL%/sdk/falcondb.js
```

Keep your settings in environment variables (Vite example):

```bash
# .env.local
VITE_FALCONDB_URL=%BASE_URL%
VITE_FALCONDB_REF=PROJECT_REF
VITE_FALCONDB_KEY=ANON_KEY
```

## 2. One shared client

```js
// src/db.js
import { createClient } from "./falcondb.js"

export const db = createClient(
  import.meta.env.VITE_FALCONDB_URL,
  import.meta.env.VITE_FALCONDB_REF,
  import.meta.env.VITE_FALCONDB_KEY,
)
```

Create it once: the client keeps the user session, and every component should share it.

## 3. A `useQuery` hook

```jsx
// src/useQuery.js
import { useEffect, useState, useCallback } from "react"

export function useQuery(buildQuery, deps = []) {
  const [state, setState] = useState({ data: null, count: 0, error: null, loading: true })

  const run = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }))
    const { data, count, error } = await buildQuery()
    setState({ data, count, error, loading: false })
  }, deps)

  useEffect(() => { run() }, [run])
  return { ...state, refresh: run }
}
```

## 4. A product list with search

```jsx
import { useState } from "react"
import { db } from "./db"
import { useQuery } from "./useQuery"

export function Products() {
  const [search, setSearch] = useState("")
  const { data, count, loading, error } = useQuery(
    () => db.from("products").select("id,name,price").ilike("name", `%${search}%`).order("name").limit(50),
    [search],
  )

  return (
    <section>
      <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search" />
      {loading && <p>Loading…</p>}
      {error && <p role="alert">{error.message}</p>}
      <p>{count} products</p>
      <ul>{data?.map((p) => <li key={p.id}>{p.name} — {p.price} €</li>)}</ul>
    </section>
  )
}
```

## 5. Follow the signed-in user

`db.auth.onChange` fires on sign in and sign out. Wrap it in a hook:

```jsx
import { useEffect, useState } from "react"
import { db } from "./db"

export function useUser() {
  const [user, setUser] = useState(db.auth.user)
  useEffect(() => db.auth.onChange(setUser), [])   // returns the unsubscribe function
  return user
}

export function Account() {
  const user = useUser()
  if (!user) {
    return <button onClick={() => db.auth.signIn({ email: "ana@example.com", password: "secret123" })}>Sign in</button>
  }
  return <p>{user.email} <button onClick={() => db.auth.signOut()}>Sign out</button></p>
}
```

## Notes for Next.js

- Use the anon key in client components (`"use client"`).
- Use the **service key** only in server code (route handlers, server actions) and read it from a non-public variable, for example `FALCONDB_SERVICE_KEY` without the `NEXT_PUBLIC_` prefix.
- The REST API works the same with plain `fetch` on the server, see the REST API tutorial.

## CORS

By default any origin may call the API. In production you can restrict it with the `FALCONDB_CORS_ORIGINS` setting, for example `https://app.example.com`.
