---
title: "falcondatabase 0.6: portals, file storage and analytics"
date: 2026-10-25
category: news
summary: Turn projects into apps, store files, measure your websites and move projects between servers. Here's everything new in 0.5 and 0.6.
tags: release, announcement
---
The last two releases add the pieces people asked for most: somewhere to keep files, a way to give non-developers access to their data, and numbers about the websites built on falcondatabase.

## Version 0.6

**Portal.** Any project can become a standalone app at `/app/<username>/<address>/`. Its users sign in and get a list of the tables you share, with search and forms generated from the columns. Each table is hidden, view-only or editable, and Owner tables keep every user's rows private. → *Tutorial: turn a project into an app with the Portal*

**File storage.** Public and private buckets, a file browser in the dashboard, uploads from your app with `db.storage.from(bucket).upload()`, and signed links that expire. → *Tutorial: store files in buckets, a simpler S3*

## Version 0.5

**Web analytics.** A 1 KB script with no cookies gives each project charts for sessions, users and pageviews, plus countries, sources, pages and devices. The new **Analytics** page combines all your projects. → *Tutorial: privacy-friendly web analytics for your website*

**Export and import.** Download a project as JSON, with or without data, and recreate it anywhere. → *Guide: export and import projects as JSON*

**Dashboard KPIs.** Ten numbers at the top of your dashboard: projects, tables, rows, storage, app users, new and active users, visitors, pageviews and bounce rate, with their change over the last 30 days.

**Profile pictures**, and a **Versions** page linked from the menu. The current version also appears in the footer, so you always know what's running.

## Fixes

- Opening **Settings** no longer jumps to the password field.
- Date labels no longer overlap on 30- and 90-day charts.

## Upgrading

Self-hosting with Docker? Update in two commands. Your data and settings are kept:

```bash
git pull
./install.sh
```

New in the Docker setup: a `storage` volume for uploaded files. Add it to your backups as described in `DEPLOY.md`.
