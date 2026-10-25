---
title: "Tutorial: the Chrome extension, your statistics one click away"
date: 2026-10-25
category: tutorial
summary: Install the falcondatabase extension, sign in once and check the visits to your projects from the browser toolbar.
tags: chrome, extension, analytics, tutorial
---
The falcondatabase extension puts the analytics of your projects in the browser toolbar: no tab to open, no dashboard to navigate. Its icon even shows how many pageviews your sites got today.

## What it shows

- **Four key indicators**: visitors, sessions, pageviews and bounce rate, each compared with the previous period.
- **A daily chart** of pageviews. Move the mouse over it to read any day.
- **Top pages, sources and countries**.
- **Filters**: all your projects or just one, and the last 7, 14, 30 or 90 days.
- **A badge on the icon** with today's pageviews, refreshed every 30 minutes.
- A link to the full analytics in the dashboard.

It includes the projects other people shared with you, and it's available in English and Spanish, in light and dark mode.

## How to install it

The extension isn't in the Chrome Web Store yet, so Chrome installs it in **developer mode**. It takes a minute:

1. On the home page of your server, click **Get the Chrome extension**, or go to %BASE_URL%/extension/.
2. Click **Download the extension**. The zip comes **pre-configured for your server**, so you won't have to type its address.
3. **Unzip** it. You get a folder called `falcondatabase-extension`. Keep it somewhere permanent (for example, in Documents): Chrome loads the extension from there.
4. Type `chrome://extensions` in the address bar and turn on **Developer mode** (top right).
5. Click **Load unpacked** and choose the `falcondatabase-extension` folder.
6. Click the puzzle icon in the toolbar and **pin** falcondatabase so it's always visible.

It also works in Edge, Brave, Opera and other Chromium browsers (`edge://extensions`, `brave://extensions`…).

## Sign in

Click the icon and enter your falcondatabase **username or email** and **password**.

- If you have **two-step authentication**, the extension asks for the 6-digit code from your app, exactly like the website.
- The first time, Chrome may ask for permission to connect to your server: accept it.
- The session lasts **30 days**. Changing your password signs the extension out everywhere.
- **Sign out** removes the session from the browser.

## How it works

The extension only talks to **your** server, never to a third party:

1. When you sign in, it calls `POST /api/account/token` and keeps the token it receives in Chrome's local storage.
2. Every time you open it, it calls `GET /api/account/analytics` with that token and draws the numbers.
3. A background worker repeats the call every 30 minutes to update the badge.

The token only gives access to your analytics, nothing else. The extension's code is in the `extension/` folder of the repository (Manifest V3), if you want to review or change it.

## Updating it

When there's a new version, download the zip again, replace the folder, and click the **reload** arrow of the extension in `chrome://extensions`. You stay signed in.

## Troubleshooting

| Problem | Solution |
|---|---|
| "Invalid or expired token" | Sign in again (it happens after 30 days or after changing your password) |
| "The extension needs permission…" | Accept the permission prompt, or remove and load the extension again |
| All numbers are zero | Enable **Analytics** in your projects and add the script to your sites |
| The badge shows "!" | The session expired: open the extension and sign in |
