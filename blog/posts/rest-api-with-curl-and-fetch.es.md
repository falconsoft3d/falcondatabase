---
title: "Tutorial: la API REST con curl y fetch"
date: 2026-09-19
category: tutorial
summary: Usa falcondatabase desde cualquier lenguaje. Cada endpoint, cabecera y filtro explicado con ejemplos de curl y fetch.
tags: api, rest, curl
---
El SDK de JavaScript es solo una capa fina sobre una API REST normal. Si trabajas con Python, PHP, Go, una app móvil o un script de shell, esto es todo lo que necesitas.

## URL base y cabeceras

```
%BASE_URL%/api/v1/PROJECT_REF
```

Cada petición envía la cabecera **apikey**. Las peticiones en nombre de un usuario con sesión envían además su token:

```
apikey: ANON_KEY
Authorization: Bearer TOKEN_DEL_USUARIO
```

La **service key** da acceso total e ignora las reglas de acceso. Guárdala en tus servidores.

## Listar filas

```bash
curl "%BASE_URL%/api/v1/PROJECT_REF/tables/productos?precio=gte.10&order=precio.desc&limit=20" \
  -H "apikey: ANON_KEY"
```

Los filtros tienen la forma `columna=operador.valor`:

| Ejemplo | Significado |
|---|---|
| `precio=gte.10` | precio ≥ 10 |
| `nombre=ilike.%25cafe%25` | el nombre contiene "cafe" (`%25` es `%` codificado) |
| `stock=is.null` | stock es NULL |
| `categoria=in.(bebidas,postres)` | categoría es una de la lista |
| `activo=eq.true` | coincidencia exacta (`activo=true` también funciona) |

Otros parámetros: `select=id,nombre`, `order=precio.desc,nombre.asc`, `limit` (100 por defecto, máximo 1000) y `offset`.

La respuesta siempre tiene la misma forma:

```json
{"data": [ ... ], "count": 42}
```

## Insertar

```bash
curl -X POST "%BASE_URL%/api/v1/PROJECT_REF/tables/productos" \
  -H "apikey: SERVICE_KEY" -H "Content-Type: application/json" \
  -d '{"nombre": "Té", "precio": 6.9}'
```

Envía una **lista** JSON para insertar varias filas en una sola transacción: si una falla, no se guarda ninguna. La respuesta es `201` con las filas creadas, incluidos `id` y `created_at`.

## Obtener, actualizar y eliminar una fila

```bash
curl "%BASE_URL%/api/v1/PROJECT_REF/tables/productos/7" -H "apikey: ANON_KEY"

curl -X PATCH "%BASE_URL%/api/v1/PROJECT_REF/tables/productos/7" \
  -H "apikey: SERVICE_KEY" -H "Content-Type: application/json" -d '{"precio": 7.5}'

curl -X DELETE "%BASE_URL%/api/v1/PROJECT_REF/tables/productos/7" -H "apikey: SERVICE_KEY"
```

## Usuarios

| Método | Ruta | Cuerpo → resultado |
|---|---|---|
| POST | `/auth/signup` | `{"email", "password", "data"?}` → `{user, token, expires_in}` |
| POST | `/auth/login` | `{"email", "password"}` → `{user, token, expires_in}` |
| GET | `/auth/user` | usuario actual (requiere el token) |
| PATCH | `/auth/user` | `{"data": {...}}` combina datos del perfil |

Los tokens duran 7 días por defecto.

## Lo mismo con fetch

```js
const BASE = "%BASE_URL%/api/v1/PROJECT_REF"
const headers = { apikey: "ANON_KEY", "Content-Type": "application/json" }

const res = await fetch(`${BASE}/tables/productos?order=precio.desc`, { headers })
const { data, count, error } = await res.json()
```

## Errores

Los errores llegan como JSON con un código HTTP: `{"error": "mensaje"}`.

| Código | Cuándo |
|---|---|
| 400 | filtro inválido, columna desconocida, valor de tipo incorrecto |
| 401 | falta la clave o es inválida, o la tabla requiere un usuario con sesión |
| 403 | tabla privada, login desactivado, registro desactivado |
| 404 | proyecto, tabla o fila desconocidos |
| 409 | email ya registrado |

Los mensajes salen en español o inglés según la cabecera `Accept-Language`.
