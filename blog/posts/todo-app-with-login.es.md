---
title: "Tutorial: una app de tareas con login en un solo HTML"
date: 2026-10-03
category: tutorial
summary: Registro, inicio de sesión y tareas privadas por usuario, con la regla de acceso Dueño y unas 60 líneas de JavaScript.
tags: auth, dueño, javascript, tutorial
---
Vamos a construir una app de tareas completa: los usuarios se registran, inician sesión y gestionan tareas que nadie más puede ver. Sin framework, sin build, un solo archivo HTML.

## 1. Prepara el proyecto

En tu proyecto:

1. Pestaña **Autenticación** → marca **Activar login** y **Permitir registro público**, y pulsa **Guardar**.
2. **Tablas** → **Nueva tabla** llamada `tareas` con las columnas:
    - `titulo` — `text`, obligatoria,
    - `hecha` — `boolean`, por defecto `false`.
3. Acceso desde la API: **Dueño — cada usuario solo ve y edita sus propias filas**.

La regla Dueño agrega una columna `owner_id` que falcondatabase rellena por ti.

## 2. La página

Guarda esto como `tareas.html`, reemplaza `PROJECT_REF` y `ANON_KEY`, y ábrelo con cualquier servidor estático (por ejemplo `python3 -m http.server`).

```html
<!doctype html>
<html>
<body>
  <form id="auth">
    <input id="email" type="email" placeholder="email" required>
    <input id="password" type="password" placeholder="contraseña" required minlength="6">
    <button name="action" value="in">Entrar</button>
    <button name="action" value="up">Registrarme</button>
  </form>

  <section id="app" hidden>
    <p>Hola <b id="who"></b> · <button id="logout">Salir</button></p>
    <form id="new"><input id="titulo" placeholder="Nueva tarea" required> <button>Agregar</button></form>
    <ul id="list"></ul>
  </section>

  <script type="module">
    import { createClient } from "%BASE_URL%/sdk/falcondb.js"
    const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
    const $ = (id) => document.getElementById(id)

    async function render() {
      const conSesion = Boolean(db.auth.user)
      $("auth").hidden = conSesion
      $("app").hidden = !conSesion
      if (!conSesion) return
      $("who").textContent = db.auth.user.email
      const { data } = await db.from("tareas").select().order("created_at")
      $("list").innerHTML = ""
      for (const tarea of data) {
        const li = document.createElement("li")
        li.innerHTML = `<input type="checkbox" ${tarea.hecha ? "checked" : ""}> <span></span> <button>✕</button>`
        li.querySelector("span").textContent = tarea.titulo
        li.querySelector("input").onchange = (e) => db.from("tareas").update(tarea.id, { hecha: e.target.checked })
        li.querySelector("button").onclick = async () => { await db.from("tareas").delete(tarea.id); render() }
        $("list").append(li)
      }
    }

    $("auth").onsubmit = async (event) => {
      event.preventDefault()
      const credenciales = { email: $("email").value, password: $("password").value }
      const accion = event.submitter.value === "up" ? db.auth.signUp : db.auth.signIn
      const { error } = await accion.call(db.auth, credenciales)
      if (error) alert(error.message)
    }
    $("new").onsubmit = async (event) => {
      event.preventDefault()
      await db.from("tareas").insert({ titulo: $("titulo").value })
      $("titulo").value = ""
      render()
    }
    $("logout").onclick = () => db.auth.signOut()

    db.auth.onChange(render)   // vuelve a pintar al entrar o salir
    render()
  </script>
</body>
</html>
```

## 3. Qué acaba de pasar

- `signUp` y `signIn` guardan la sesión en `localStorage`, así que al recargar sigues dentro.
- Desde ese momento cada petición lleva `Authorization: Bearer <token>` automáticamente.
- `insert({ titulo })` nunca envía `owner_id`; el servidor lo pone a partir del token.
- `select()` solo devuelve las filas del usuario actual. Abre la página en una ventana privada con otra cuenta: las listas son independientes.

## 4. Revísalo desde el dashboard

Abre la tabla `tareas` en el dashboard: ves todas las tareas con su `owner_id`. La pestaña **Autenticación** lista los usuarios, su último acceso y te permite desactivar una cuenta. El token de un usuario desactivado deja de funcionar al instante.

## Ideas para ampliarla

- Guarda un nombre al registrarse: `db.auth.signUp({ email, password, data: { nombre } })`.
- Actualízalo después con `db.auth.updateUser({ nombre: "Ana" })`.
- Agrega una columna `vence` de tipo `date` y ordena con `.order("vence")`.
