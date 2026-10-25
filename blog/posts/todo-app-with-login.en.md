---
title: "Tutorial: a to-do app with login in one HTML file"
date: 2026-10-03
category: tutorial
summary: Sign up, sign in and private tasks per user, using the Owner access rule and about 60 lines of JavaScript.
tags: auth, owner, javascript, tutorial
---
We'll build a complete to-do app: users register, sign in and manage tasks that nobody else can see. No framework, no build step, one HTML file.

## 1. Prepare the project

In your project:

1. **Authentication** tab → check **Enable login** and **Allow public sign up**, then **Save**.
2. **Tables** → **New table** named `todos` with columns:
    - `title` — `text`, required,
    - `done` — `boolean`, default `false`.
3. API access: **Owner — each user only sees and edits their own rows**.

The Owner rule adds an `owner_id` column that falcondatabase fills in for you.

## 2. The page

Save this as `todo.html`, replace `PROJECT_REF` and `ANON_KEY`, and open it with any static server (for example `python3 -m http.server`).

```html
<!doctype html>
<html>
<body>
  <form id="auth">
    <input id="email" type="email" placeholder="email" required>
    <input id="password" type="password" placeholder="password" required minlength="6">
    <button name="action" value="in">Sign in</button>
    <button name="action" value="up">Sign up</button>
  </form>

  <section id="app" hidden>
    <p>Hi <b id="who"></b> · <button id="logout">Sign out</button></p>
    <form id="new"><input id="title" placeholder="New task" required> <button>Add</button></form>
    <ul id="list"></ul>
  </section>

  <script type="module">
    import { createClient } from "%BASE_URL%/sdk/falcondb.js"
    const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
    const $ = (id) => document.getElementById(id)

    async function render() {
      const signedIn = Boolean(db.auth.user)
      $("auth").hidden = signedIn
      $("app").hidden = !signedIn
      if (!signedIn) return
      $("who").textContent = db.auth.user.email
      const { data } = await db.from("todos").select().order("created_at")
      $("list").innerHTML = ""
      for (const todo of data) {
        const li = document.createElement("li")
        li.innerHTML = `<input type="checkbox" ${todo.done ? "checked" : ""}> <span></span> <button>✕</button>`
        li.querySelector("span").textContent = todo.title
        li.querySelector("input").onchange = (e) => db.from("todos").update(todo.id, { done: e.target.checked })
        li.querySelector("button").onclick = async () => { await db.from("todos").delete(todo.id); render() }
        $("list").append(li)
      }
    }

    $("auth").onsubmit = async (event) => {
      event.preventDefault()
      const credentials = { email: $("email").value, password: $("password").value }
      const action = event.submitter.value === "up" ? db.auth.signUp : db.auth.signIn
      const { error } = await action.call(db.auth, credentials)
      if (error) alert(error.message)
    }
    $("new").onsubmit = async (event) => {
      event.preventDefault()
      await db.from("todos").insert({ title: $("title").value })
      $("title").value = ""
      render()
    }
    $("logout").onclick = () => db.auth.signOut()

    db.auth.onChange(render)   // re-render on sign in / sign out
    render()
  </script>
</body>
</html>
```

## 3. What just happened

- `signUp` and `signIn` store the session in `localStorage`, so a reload keeps you signed in.
- Every request after that carries `Authorization: Bearer <token>` automatically.
- `insert({ title })` never sends `owner_id`; the server sets it from the token.
- `select()` only returns the current user's rows. Open the page in a private window with another account: the lists are separate.

## 4. Check it from the dashboard

Open the `todos` table in the dashboard: you see every task with its `owner_id`. The **Authentication** tab lists the users, their last login, and lets you deactivate an account. A deactivated user's token stops working immediately.

## Ideas to extend it

- Store a display name at sign up: `db.auth.signUp({ email, password, data: { name } })`.
- Update it later with `db.auth.updateUser({ name: "Ana" })`.
- Add a `due_date` column of type `date` and sort with `.order("due_date")`.
