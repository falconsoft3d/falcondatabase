---
title: "Tutorial: store files in buckets, a simpler S3"
date: 2026-10-25
category: tutorial
summary: Upload images and documents from your app or the dashboard, share them with public URLs or links that expire, and keep private files private.
tags: storage, files, javascript, tutorial
---
Most apps need files: profile pictures, product photos, invoices, attachments. Each project has **Storage** for that: buckets with folders, a file browser in the dashboard, and the same `db` client you already use for tables.

## 1. Enable storage and create a bucket

Open your project → **Storage** tab → check **Enable storage** → **Save**. Then create a bucket:

- **Public** buckets: every file has a direct URL that anyone can open. Use them for images on your website.
- **Private** buckets: files are only served to the user who uploaded them, with the service key, or through a **signed link** that expires. Use them for invoices, documents and anything personal.

Bucket names use lowercase letters, numbers and hyphens, like `avatars` or `invoices-2026`.

## 2. Upload from the dashboard

Open the bucket to get a file browser:

- Select one or more files and, optionally, a **folder** (for example `products/2026`). Folders are created automatically.
- **URL** copies the public link (public buckets). **Link** creates a link valid for one hour (private buckets).
- Download or delete any file, make the bucket public or private, or delete it.

Files with the same name are replaced.

## 3. Upload from your app

Uploads need a **signed-in user** of your app (or the service key on a server):

```html
<input type="file" id="picture" accept="image/*">
<img id="preview" width="96">

<script type="module">
  import { createClient } from "%BASE_URL%/sdk/falcondb.js"
  const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
  await db.auth.signIn({ email: "ana@example.com", password: "secret123" })

  const avatars = db.storage.from("avatars")   // a public bucket
  document.getElementById("picture").onchange = async (event) => {
    const path = `users/${db.auth.user.id}.png`
    const { error } = await avatars.upload(path, event.target.files[0], { upsert: true })
    if (error) return alert(error.message)
    document.getElementById("preview").src = avatars.getPublicUrl(path) + "?t=" + Date.now()
  }
</script>
```

`upsert: true` replaces the file if it exists. Without it, uploading to an existing path returns an error.

## 4. Private files and signed links

```js
const invoices = db.storage.from("invoices")          // a private bucket
await invoices.upload("2026/10/inv-001.pdf", file)
const { data: link } = await invoices.createSignedUrl("2026/10/inv-001.pdf", 600)  // 10 minutes
window.open(link)
```

Each user only lists, shares and deletes **their own** files in a private bucket. Signed links work for anyone who has them, until they expire (maximum 7 days).

## 5. The rest of the SDK

```js
const bucket = db.storage.from("avatars")
const { data: files } = await bucket.list("users")        // files under a folder
const { data: blob } = await bucket.download("users/1.png")
await bucket.remove("users/1.png")
const { data: buckets } = await db.storage.listBuckets()
```

## Who can do what

| | Public bucket | Private bucket |
|---|---|---|
| Download | anyone with the URL | the uploader, the service key, or a signed link |
| List | any key | the service key (all files) or the user (their files) |
| Upload | signed-in user or service key | same |
| Delete / replace | the uploader or the service key | same |

## Limits and safety

- 50 MB per file and 1 GB per project by default. Self-hosters can change both with `FALCONDB_STORAGE_MAX_FILE_MB` and `FALCONDB_STORAGE_QUOTA_MB`.
- Files are stored under random names on the server; the path you choose is only a label.
- HTML, SVG and JavaScript files are always downloaded, never opened in the browser, so an uploaded file can't run code on your domain.
- Stored files aren't included in project exports. Back them up with the server backups (see the Docker tutorial).
