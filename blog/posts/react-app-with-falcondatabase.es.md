---
title: "Tutorial: usa falcondatabase desde React"
date: 2026-10-08
category: tutorial
summary: Un cliente compartido, un pequeño hook useQuery y un componente que reacciona al login, para apps React o Next.js.
tags: react, javascript, frontend
---
El SDK no depende de ningún framework, así que encaja de forma natural en React. En este tutorial crearemos un cliente compartido, un hook reutilizable y un componente que reacciona al inicio y cierre de sesión.

## 1. Agrega el SDK a tu proyecto

Descarga el módulo una vez dentro de tu código, para que tu bundler pueda importarlo:

```bash
curl -o src/falcondb.js %BASE_URL%/sdk/falcondb.js
```

Guarda la configuración en variables de entorno (ejemplo con Vite):

```bash
# .env.local
VITE_FALCONDB_URL=%BASE_URL%
VITE_FALCONDB_REF=PROJECT_REF
VITE_FALCONDB_KEY=ANON_KEY
```

## 2. Un cliente compartido

```js
// src/db.js
import { createClient } from "./falcondb.js"

export const db = createClient(
  import.meta.env.VITE_FALCONDB_URL,
  import.meta.env.VITE_FALCONDB_REF,
  import.meta.env.VITE_FALCONDB_KEY,
)
```

Créalo una sola vez: el cliente guarda la sesión del usuario y todos los componentes deben compartirlo.

## 3. Un hook `useQuery`

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

## 4. Una lista de productos con búsqueda

```jsx
import { useState } from "react"
import { db } from "./db"
import { useQuery } from "./useQuery"

export function Productos() {
  const [busqueda, setBusqueda] = useState("")
  const { data, count, loading, error } = useQuery(
    () => db.from("productos").select("id,nombre,precio").ilike("nombre", `%${busqueda}%`).order("nombre").limit(50),
    [busqueda],
  )

  return (
    <section>
      <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} placeholder="Buscar" />
      {loading && <p>Cargando…</p>}
      {error && <p role="alert">{error.message}</p>}
      <p>{count} productos</p>
      <ul>{data?.map((p) => <li key={p.id}>{p.nombre} — {p.precio} €</li>)}</ul>
    </section>
  )
}
```

## 5. Sigue al usuario con sesión

`db.auth.onChange` se dispara al iniciar y cerrar sesión. Envuélvelo en un hook:

```jsx
import { useEffect, useState } from "react"
import { db } from "./db"

export function useUsuario() {
  const [usuario, setUsuario] = useState(db.auth.user)
  useEffect(() => db.auth.onChange(setUsuario), [])   // devuelve la función para desuscribirse
  return usuario
}

export function Cuenta() {
  const usuario = useUsuario()
  if (!usuario) {
    return <button onClick={() => db.auth.signIn({ email: "ana@ejemplo.com", password: "secreto123" })}>Entrar</button>
  }
  return <p>{usuario.email} <button onClick={() => db.auth.signOut()}>Salir</button></p>
}
```

## Notas para Next.js

- Usa la anon key en componentes de cliente (`"use client"`).
- Usa la **service key** solo en código de servidor (route handlers, server actions) y léela de una variable no pública, por ejemplo `FALCONDB_SERVICE_KEY`, sin el prefijo `NEXT_PUBLIC_`.
- La API REST funciona igual con `fetch` en el servidor; mira el tutorial de la API REST.

## CORS

Por defecto cualquier origen puede llamar a la API. En producción puedes restringirlo con la variable `FALCONDB_CORS_ORIGINS`, por ejemplo `https://app.ejemplo.com`.
