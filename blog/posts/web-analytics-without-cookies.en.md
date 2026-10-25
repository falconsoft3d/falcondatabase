---
title: "Tutorial: privacy-friendly web analytics for your website"
date: 2026-10-25
category: tutorial
summary: Add one script tag to your site and get sessions, users, pageviews, countries, sources and devices, with no cookies and no banner.
tags: analytics, privacy, tutorial
---
Every project can measure the traffic of the websites that use it. The tracking script is about 1 KB, sets **no cookies** and stores **no IP addresses**, so your visitors don't need to accept a cookie banner for it.

## 1. Enable analytics

Open your project → **Analytics** tab → check **Enable analytics** → **Save**.

Optionally fill in **Allowed domains** (for example `example.com, shop.example.com`). Only visits from those domains and their subdomains will be counted, so nobody can pollute your numbers by copying the snippet.

## 2. Add the script to your site

Paste this in the `<head>` of every page:

```html
<script defer data-project="PROJECT_REF" src="%BASE_URL%/a.js"></script>
```

The Analytics tab shows the snippet with your real `PROJECT_REF`, ready to copy.

Single-page apps (React, Vue, Svelte…) are supported: the script also counts client-side navigations made with `history.pushState` and the back/forward buttons.

## 3. Read the dashboard

Pick a period (**7, 14, 30 or 90 days**). Each number is compared with the previous period of the same length.

| Indicator | Meaning |
|---|---|
| Visitors | Unique visitors per day |
| Sessions | Visits; a session ends after 30 minutes without activity |
| Pageviews | Every page load or navigation |
| Pages / session | Pageviews divided by sessions |
| Bounce rate | Sessions with a single pageview (lower is better) |

Below, three daily charts (sessions, users, pageviews) show the trend. Hover them to read each day, or open **Show as table**. Then come the breakdowns:

- **Countries**: from your CDN header (`CF-IPCountry`) if you use one, otherwise from the browser time zone, otherwise from the browser language.
- **Mediums**: Direct, Organic search, Social, Referral, Paid search, Email…
- **Sources**: Google, LinkedIn, github.com, newsletter…
- **Top pages**, **devices**, **browsers** and **operating systems**.

## 4. Track your campaigns with UTM parameters

Add UTM parameters to the links you share, and the session takes its source and medium from them:

```
https://example.com/?utm_source=newsletter&utm_medium=email&utm_campaign=october
```

`utm_medium=cpc` appears as **Paid search** and `utm_medium=email` as **Email**.

## 5. All your projects at once

**Analytics** in the main menu (`/analytics/`) combines every project. Tick the projects you want to compare, or leave them all unticked to see everything, and the **By project** list shows which one gets the most traffic.

## How privacy is protected

- No cookies, `localStorage` or fingerprinting scripts.
- The visitor id is a one-way hash of the day, the project, the IP and the browser. It changes every day, so visitors can't be followed from one day to the next. That's also why "visitors" means unique visitors *per day*.
- The page path is stored without its query string.
- Bots and crawlers are ignored.

> **Self-hosting behind a proxy?** Make sure `FALCONDB_TRUST_PROXY=true` (automatic when `USE_HTTPS=true`). Otherwise every visit looks like it comes from the proxy.

## Try it with sample data

If you run your own server and want to see the charts before installing the script anywhere:

```bash
python manage.py seed_analytics <username>/<project-slug> --days 30
```
