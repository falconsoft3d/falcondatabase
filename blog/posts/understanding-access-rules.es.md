---
title: "Guía: entiende las reglas de acceso"
date: 2026-09-26
category: guide
summary: Pública, lectura pública, usuarios con login, dueño o privada. Elige la regla correcta para cada tabla antes de publicar.
tags: seguridad, reglas-de-acceso, auth
---
La **anon key** vive en tu frontend, así que cualquiera puede leerla. Lo que protege tus datos es la **regla de acceso** de cada tabla. La eliges al crear la tabla y puedes cambiarla cuando quieras desde la pestaña **Estructura**.

## Las cinco reglas

| Regla | Leer | Escribir | Uso típico |
|---|---|---|---|
| **Pública** | cualquiera | cualquiera | prototipos, libros de visitas |
| **Lectura pública** | cualquiera | usuarios con login | catálogos, artículos, comentarios |
| **Usuarios con login** | usuarios con login | usuarios con login | herramientas internas, contenido para miembros |
| **Dueño** | solo sus filas | solo sus filas | tareas, notas, pedidos, perfiles |
| **Privada** | service key | service key | datos que solo toca tu backend |

Los "usuarios con login" son los usuarios de *tu app* (pestaña **Autenticación** del proyecto), no cuentas de falcondatabase. Sus peticiones incluyen `Authorization: Bearer <token>`.

La **service key** se salta todas las reglas. Úsala en código de servidor, tareas programadas y scripts de administración, nunca en un navegador.

## Cómo funciona "Dueño"

Al elegir **Dueño**, falcondatabase agrega una columna `owner_id` a la tabla. Entonces:

1. Al insertar, `owner_id` se rellena automáticamente con el usuario con sesión. Lo que envíe el cliente se ignora.
2. Las lecturas solo devuelven filas cuyo `owner_id` es el usuario actual.
3. Las actualizaciones y borrados solo afectan a las filas del usuario. La fila de otra persona se comporta como si no existiera (`404`).

```js
await db.auth.signIn({ email, password })
await db.from("notas").insert({ texto: "Comprar leche" })   // owner_id se rellena solo
const { data } = await db.from("notas").select()              // solo mis notas
```

Con la service key ves todas las filas, incluido `owner_id`, ideal para paneles de administración.

## Qué pasa cuando se deniega el acceso

| Situación | Respuesta |
|---|---|
| Petición anónima a una tabla que requiere usuario | `401 Necesitas iniciar sesión para esta operación.` |
| Cualquier petición con la anon key a una tabla **Privada** | `404` (la tabla queda oculta) |
| Token caducado o inválido | `401 Token inválido o expirado.` |

## Las columnas del sistema están protegidas

Los clientes con la anon key no pueden escribir `id`, `created_at` ni `owner_id`. Esas claves se quitan en silencio de inserciones y actualizaciones, así nadie puede robar una fila cambiando su dueño.

## Lista de control antes de publicar

- Empieza por **Lectura pública** o algo más estricto. Usa **Pública** solo para datos que cualquiera puede cambiar.
- Guarda los datos de cada usuario en tablas **Dueño**.
- Usa **Privada** más la service key para todo lo sensible.
- Desactiva **Permitir registro público** en la pestaña Autenticación si solo tú debes crear usuarios.
- Regenera las claves desde **Configuración** si la service key se filtra alguna vez.
