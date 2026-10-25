---
title: "Tutorial: work as a team and follow your contributions"
date: 2026-10-25
category: tutorial
summary: Share a project with other accounts as editor or viewer, and see a GitHub-style graph of everything that changes.
tags: teams, sharing, activity, tutorial
---
Projects don't have to be a one-person job. You can invite other falcondatabase accounts to a project and decide what they can do, and a contribution graph shows how active each project is.

## Share a project

1. Open the project → **Settings** → **Members**.
2. Type the **email** of the other person's account and pick a role.
3. Click **Share**.

The person must already have an account on the server. If they don't, ask them to sign up first (or, if sign up is closed, ask the administrator to create the account).

| Role | What they can do |
|---|---|
| **Editor** | Work inside the project: tables, rows, structure, app users, analytics, storage and portal settings |
| **Viewer** | Open every page and read the data, but change nothing |
| **Owner** (you) | Everything, plus Settings: rename, API keys, export, members and deleting the project |

The project then appears under **Shared with you** on their dashboard, in their **Analytics** page and in the Chrome extension. A banner reminds viewers that their access is read-only.

You can change a member's role or remove them in **Settings → Members** at any time, and members can leave a project from its **Overview**.

## Your contribution graph

The dashboard shows a graph like GitHub's: one square per day of the last year, darker (or brighter in dark mode) the more changes happened that day. Hover a square to see the exact number and date.

Use the picker above the graph to see **all your projects** or **just one**. Each project's **Overview** also has its own graph.

## What counts as a contribution

Every change to a project, wherever it comes from:

- creating or deleting tables, adding or removing columns;
- inserting, updating or deleting rows, **from the dashboard, the REST API or the portal**;
- uploading or deleting files and creating buckets;
- adding app users and sharing the project.

Inserting 50 rows in one request counts as **one** contribution, like a commit with many lines.

## Recent activity

Below the graph, each project's **Overview** lists the latest changes and who made them:

- **ana** inserted rows in `orders` (×12) · 3 minutes ago
- **API (service key)** updated a row in `products` · 1 hour ago
- **eva@example.com** deleted a row from `tasks` · yesterday

Changes made by dashboard accounts show their username. Changes made by the users of your app show their email, and calls with API keys show "API".

## Your history is already there

Projects created before this feature get their history rebuilt from the dates already stored (when tables, rows, files and users were created), so your graph doesn't start empty.
