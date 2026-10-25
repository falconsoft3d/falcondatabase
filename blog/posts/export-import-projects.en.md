---
title: "Guide: export and import projects as JSON"
date: 2026-10-25
category: guide
summary: Copy a project's structure, and optionally its data, to a file. Use it as a template, move it to another server or start a new environment.
tags: json, export, import, migration
---
Every project can be saved as a single JSON file and recreated from it, on the same server or on another one. It's the quickest way to reuse a structure, share a template or set up a test copy.

## Export

Open the project → **Settings** → **Export**:

- **Export structure**: project settings, tables, columns, defaults, constraints, access rules and portal modes, plus the bucket definitions.
- **Export structure and data**: the same, plus every row of every table.

The file looks like this:

```json
{
  "format": "falcondatabase",
  "version": 1,
  "project": { "name": "Shop", "description": "", "auth_enabled": true, "storage_enabled": true },
  "tables": [
    {
      "name": "products",
      "access": "public_read",
      "portal_mode": "view",
      "columns": [
        { "name": "name", "type": "text", "required": true, "unique": true, "default": null },
        { "name": "price", "type": "decimal", "required": false, "unique": false, "default": "0" },
        { "name": "code", "type": "uuid", "required": false, "unique": false, "default": "uuid()" }
      ],
      "rows": [{ "id": 1, "created_at": "2026-10-25T10:00:00Z", "name": "Coffee", "price": "12.50" }]
    }
  ],
  "buckets": [{ "name": "images", "public": true }]
}
```

## What is not exported

| Not included | Why |
|---|---|
| The users of your app | They contain password hashes |
| Files in Storage | They can be large; back them up with the server |
| Analytics | It belongs to the original project |
| Portal address and API keys | They must be unique; the copy gets new ones |

## Import

Go to **New project** → **Or import a project from JSON**, choose the file and, optionally, a new name.

- Everything is created in **one transaction**: if any table, column or row fails, nothing is created and you see the reason.
- Row ids are kept, and new rows continue after the highest one.
- Settings are copied (login, sign up, analytics, storage, public portal), but the portal starts **disabled** until you choose its address.
- In tables with the Owner rule, rows lose their owner, because the users aren't copied.

The maximum file size is 20 MB. For bigger databases, use the PostgreSQL backups described in the Docker tutorial.

## Use cases

- **Templates**: keep a "CRM" or "inventory" structure and create a fresh project from it in seconds.
- **Staging**: export *structure and data*, import it on a test server, try your changes there.
- **Moving servers**: export each project, install falcondatabase on the new server, import them, then copy the files of your buckets.

The format is plain JSON, so you can also generate it from a script to create projects automatically.
