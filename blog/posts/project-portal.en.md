---
title: "Tutorial: turn a project into an app with the Portal"
date: 2026-10-25
category: tutorial
summary: Give your team or customers their own address where they sign in and view or edit your tables, with forms generated automatically.
tags: portal, no-code, tutorial
---
Sometimes you don't need a custom frontend at all: you need a place where a few people can sign in and manage some tables. That's the **Portal**: every project can become a standalone app with its own address, login, table list, search and forms, without writing code.

## 1. Enable the portal

Open the project → **Portal** tab:

1. Check **Enable portal**.
2. Choose an **address**, for example `inventory` (3 to 50 lowercase letters, numbers and hyphens).
3. For each table, choose how it appears:

| Mode | In the portal |
|---|---|
| **Hidden** | Not shown |
| **View only** | List, search and detail |
| **View and edit** | Also create, edit and delete |

4. **Save**.

Your app is now live at:

```
%BASE_URL%/app/<your-username>/inventory/
```

The address includes your username, so two people can both have an `inventory` portal.

## 2. Who can sign in

People sign in with the **users of the project** (the **Authentication** tab): create them there with an email and a password. If **Allow public sign up** is on, people can also create their own account from the portal's sign-in page.

The portal session is separate from your dashboard account: signing in to a portal never gives access to your projects or keys.

## 3. What your users see

- A sidebar with the tables you shared.
- For each table: a **search** box (it searches every column), sortable columns and 25 rows per page.
- In **View and edit** tables: a **New** button and an **Edit** button on every row. The forms are generated from the columns: text and number inputs, date pickers, true/false selectors and a JSON editor. Required fields are marked.
- Validation comes from the database: a required column left empty or a duplicate in a unique column shows a clear error.

## 4. Private rows per user

If a table uses the **Owner** access rule, each portal user only sees and edits **their own rows**, and new rows are assigned to them automatically. Use it for requests, orders, timesheets… anything personal.

## 5. Public portals

Check **Public portal** to let anyone view the **View only** tables without signing in, for example a public catalog or a list of events. Even in a public portal:

- creating, editing and deleting always require signing in;
- **Owner** tables always require signing in.

## Ideas

- **Team inventory**: `items` in *View and edit*, `suppliers` in *View only*.
- **Customer requests**: a `requests` table with the Owner rule, so each customer only sees their own.
- **Public directory**: a public portal with a *View only* `members` table.

Need more control over the design? Build your own frontend with the SDK. The portal and your custom app can use the same project at the same time.
