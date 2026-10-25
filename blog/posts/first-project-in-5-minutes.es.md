---
title: "Tutorial: tu primer proyecto en 5 minutos"
date: 2026-09-05
category: tutorial
summary: Crea una cuenta, un proyecto y una tabla, agrega filas y léelas a través de la API.
tags: primeros-pasos, dashboard
---
En este tutorial pasarás de cero a una API funcionando: una cuenta, un proyecto, una tabla `productos` con datos y una primera petición desde la terminal.

## 1. Crea tu cuenta

Abre %BASE_URL%/signup/ y elige un **usuario** (letras, números y guiones), tu email y una contraseña. Tu usuario forma parte de la URL de tus proyectos, por ejemplo `/tu-nombre/mi-tienda/`.

> Si el registro está desactivado en este servidor, pide al administrador que cree la cuenta por ti.

## 2. Crea un proyecto

Desde el dashboard pulsa **Nuevo proyecto**, ponle un nombre como `Mi tienda` y pulsa **Crear proyecto**. falcondatabase crea:

- un esquema de PostgreSQL solo para este proyecto,
- una URL de API: `%BASE_URL%/api/v1/<ref>`,
- una **anon key** (segura para el navegador) y una **service key** (secreta, solo para el servidor).

Las tres están en el recuadro **Conexión** del resumen del proyecto.

## 3. Crea una tabla

Ve a la pestaña **Tablas** y pulsa **Nueva tabla**:

1. Nombre: `productos`.
2. Columnas:
    - `nombre` — tipo `text`, marca **Oblig.** (NOT NULL),
    - `precio` — tipo `decimal`,
    - `stock` — tipo `integer`, por defecto `0`,
    - `activo` — tipo `boolean`, por defecto `true`.
3. Acceso desde la API: deja **Lectura pública** (cualquiera lee, solo usuarios con login escriben).

Cada tabla recibe automáticamente un `id` (autoincremental) y `created_at` (con `now()`).

## 4. Agrega filas

Abre la tabla y despliega **Insertar fila**. Agrega algunos productos. Puedes ordenar por cualquier columna pulsando su encabezado, editar una fila con el lápiz y borrarla con la papelera.

## 5. Lee los datos desde la API

Copia el **ref** y la **anon key** de tu proyecto y prueba:

```bash
curl "%BASE_URL%/api/v1/PROJECT_REF/tables/productos?order=precio.desc" \
  -H "apikey: ANON_KEY"
```

La respuesta se ve así:

```json
{
  "data": [
    {"id": 2, "created_at": "2026-09-05T10:00:00Z", "nombre": "Café", "precio": 12.5, "stock": 40, "activo": true}
  ],
  "count": 1
}
```

`count` es el total de filas que cumplen el filtro, sin importar la paginación.

## Siguientes pasos

- Consulta la tabla desde una página web con el SDK de JavaScript.
- Aprende la diferencia entre las cinco reglas de acceso antes de publicar tu app.
- La pestaña **API** de cada tabla muestra ejemplos listos para copiar con tus claves reales.
