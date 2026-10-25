---
title: Presentamos falcondatabase
date: 2026-09-01
category: news
summary: Una alternativa simple y autoalojada a Firebase y Supabase, hecha con Django y PostgreSQL.
tags: anuncio, postgresql, django
---
Toda app necesita las mismas piezas aburridas: una base de datos, una API para llegar a ella y una forma de que los usuarios inicien sesión. **falcondatabase** te da las tres en pocos clics, en tu propio servidor y con una interfaz que se siente como GitHub.

## ¿Por qué otro backend?

Firebase y Supabase son excelentes, pero a veces quieres algo que puedas leer de principio a fin, ejecutar en un VPS pequeño y adaptar a tus necesidades. falcondatabase es un proyecto Django normal sobre PostgreSQL:

- **Tablas reales.** Cada tabla que creas es una tabla real de PostgreSQL, no un JSON. Puedes consultarla con SQL cuando lo necesites.
- **Proyectos aislados.** Cada proyecto vive en su propio esquema de PostgreSQL, con su URL de API y sus claves.
- **Login incluido.** Activa la autenticación por email y contraseña para los usuarios de tu app con una casilla.
- **Reglas de acceso por tabla.** Pública, lectura pública, solo usuarios con login, por dueño o privada.
- **Una API REST y un SDK mínimo.** Consulta desde React, Vue, Svelte o JavaScript puro sin instalar nada.

## Lo que tienes en el dashboard

| Pestaña | Qué hace |
|---|---|
| Resumen | URL, claves y un ejemplo de inicio rápido |
| Tablas | Crear tablas, editar filas, agregar o quitar columnas |
| Autenticación | Activar el login y gestionar los usuarios de tu app |
| Analítica | Analítica web sin cookies para tus sitios |
| Almacenamiento | Buckets para imágenes, documentos y otros archivos |
| Portal | Publicar el proyecto como una app lista para sus usuarios |
| API | Referencia completa con tus claves reales |
| Configuración | Renombrar, exportar, regenerar claves o eliminar el proyecto |

Tu cuenta también puede protegerse con **autenticación en dos pasos**, y toda la interfaz está disponible en **español e inglés**, en modo claro y oscuro.

## Una muestra del SDK

```js
import { createClient } from "%BASE_URL%/sdk/falcondb.js"

const db = createClient("%BASE_URL%", "PROJECT_REF", "ANON_KEY")
const { data } = await db.from("productos").select().gte("precio", 10).order("precio", { desc: true })
```

## Por dónde seguir

Empieza con el tutorial **Tu primer proyecto en 5 minutos** y luego aprende a consultar tus datos desde JavaScript. Si quieres tu propia instancia, la guía de Docker te lleva de un servidor vacío a HTTPS con un solo script.

¿Preguntas o ideas? Escribe al autor a la dirección de contacto del pie de página.
