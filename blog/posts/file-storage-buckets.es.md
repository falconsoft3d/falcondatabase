---
title: "Tutorial: guarda archivos en buckets, un S3 más simple"
date: 2026-10-25
category: tutorial
summary: Sube imágenes y documentos desde tu app o el dashboard, compártelos con URLs públicas o enlaces que caducan, y mantén privados los archivos privados.
tags: almacenamiento, archivos, javascript, tutorial
---
La mayoría de las apps necesitan archivos: fotos de perfil, fotos de productos, facturas, adjuntos. Cada proyecto tiene **Almacenamiento** para eso: buckets con carpetas, un explorador de archivos en el dashboard y el mismo cliente `db` que ya usas para las tablas.

## 1. Activa el almacenamiento y crea un bucket

Abre tu proyecto → pestaña **Almacenamiento** → marca **Activar almacenamiento** → **Guardar**. Después crea un bucket:

- Buckets **públicos**: cada archivo tiene una URL directa que cualquiera puede abrir. Úsalos para las imágenes de tu web.
- Buckets **privados**: los archivos solo se sirven al usuario que los subió, con la service key, o mediante un **enlace firmado** que caduca. Úsalos para facturas, documentos y todo lo personal.

Los nombres de bucket usan minúsculas, números y guiones, como `avatares` o `facturas-2026`.

## 2. Sube desde el dashboard

Abre el bucket para ver un explorador de archivos:

- Selecciona uno o varios archivos y, opcionalmente, una **carpeta** (por ejemplo `productos/2026`). Las carpetas se crean solas.
- **URL** copia el enlace público (buckets públicos). **Enlace** crea un enlace válido durante una hora (buckets privados).
- Descarga o elimina cualquier archivo, haz el bucket público o privado, o elimínalo.

Los archivos con el mismo nombre se reemplazan.

## 3. Sube desde tu app

Para subir se necesita un **usuario con sesión** de tu app (o la service key en un servidor):

```html
<input type="file" id="foto" accept="image/*">
<img id="vista" width="96">

<script type="module">
  import { createClient } from "%BASE_URL%/sdk/falcondb.js"
  const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
  await db.auth.signIn({ email: "ana@ejemplo.com", password: "secreto123" })

  const avatares = db.storage.from("avatares")   // un bucket público
  document.getElementById("foto").onchange = async (event) => {
    const ruta = `usuarios/${db.auth.user.id}.png`
    const { error } = await avatares.upload(ruta, event.target.files[0], { upsert: true })
    if (error) return alert(error.message)
    document.getElementById("vista").src = avatares.getPublicUrl(ruta) + "?t=" + Date.now()
  }
</script>
```

`upsert: true` reemplaza el archivo si ya existe. Sin él, subir a una ruta existente devuelve un error.

## 4. Archivos privados y enlaces firmados

```js
const facturas = db.storage.from("facturas")          // un bucket privado
await facturas.upload("2026/10/fac-001.pdf", archivo)
const { data: enlace } = await facturas.createSignedUrl("2026/10/fac-001.pdf", 600)  // 10 minutos
window.open(enlace)
```

En un bucket privado, cada usuario solo lista, comparte y elimina **sus propios** archivos. Los enlaces firmados funcionan para quien los tenga, hasta que caducan (máximo 7 días).

## 5. El resto del SDK

```js
const bucket = db.storage.from("avatares")
const { data: archivos } = await bucket.list("usuarios")     // archivos dentro de una carpeta
const { data: blob } = await bucket.download("usuarios/1.png")
await bucket.remove("usuarios/1.png")
const { data: buckets } = await db.storage.listBuckets()
```

## Quién puede hacer qué

| | Bucket público | Bucket privado |
|---|---|---|
| Descargar | cualquiera con la URL | quien lo subió, la service key o un enlace firmado |
| Listar | cualquier clave | la service key (todo) o el usuario (sus archivos) |
| Subir | usuario con sesión o service key | igual |
| Eliminar / reemplazar | quien lo subió o la service key | igual |

## Límites y seguridad

- 50 MB por archivo y 1 GB por proyecto por defecto. Si alojas tu propio servidor puedes cambiar ambos con `FALCONDB_STORAGE_MAX_FILE_MB` y `FALCONDB_STORAGE_QUOTA_MB`.
- Los archivos se guardan con nombres aleatorios en el servidor; la ruta que eliges es solo una etiqueta.
- Los archivos HTML, SVG y JavaScript siempre se descargan, nunca se abren en el navegador, así un archivo subido no puede ejecutar código en tu dominio.
- Los archivos guardados no se incluyen al exportar un proyecto. Respáldalos con las copias de seguridad del servidor (mira el tutorial de Docker).
