# falcondatabase

Alternativa simple a Supabase/Firebase, con estilo GitHub, hecha con **Django + PostgreSQL**.

Crea proyectos, agrégales tablas reales de PostgreSQL y login de usuarios, y consulta todo desde cualquier frontend con una API REST o con el SDK de JavaScript.

## Funcionalidades

- **Home** pública y **dashboard** por usuario (`/dashboard/`).
- **Proyectos** en `/<usuario>/<proyecto>/`. Cada uno tiene su propio esquema de PostgreSQL (`proj_<ref>`), una URL de API y dos claves (`anon` y `service`).
- **Tablas**: creación con columnas tipadas (`text`, `integer`, `bigint`, `decimal`, `float`, `boolean`, `date`, `datetime`, `json`, `uuid`), editor de datos (insertar, editar, borrar, ordenar, paginar), agregar o quitar columnas.
- **Login para tus apps**: registro e inicio de sesión con email y contraseña por proyecto, gestión de usuarios desde el dashboard.
- **Reglas de acceso por tabla**: pública, lectura pública, solo usuarios con login, por dueño (`owner_id` automático) o privada.
- **API REST** con filtros (`eq`, `gt`, `ilike`, `in`…), orden, paginación y CORS.
- **SDK JavaScript** sin dependencias en `/sdk/falcondb.js`.
- **Español e inglés**: selector de idioma en la cabecera (también en la home) y en el perfil (`/settings/`). Los errores de la API siguen la cabecera `Accept-Language`.
- **Modo claro y oscuro**: sigue al sistema por defecto; se cambia con el botón de la cabecera o en el perfil.
- **Autenticación en dos pasos (TOTP)** para entrar al dashboard, compatible con Google Authenticator, Authy, 1Password… Incluye 8 códigos de recuperación de un solo uso.
- **Admin único**: ve todos los usuarios en `/users/`, crea cuentas, desactiva el registro público y puede quitar el 2FA a un usuario que perdió su teléfono.

## Puesta en marcha

Requisitos: Python 3.12+ y PostgreSQL 14+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env            # ajusta las credenciales de PostgreSQL

# Opcional: levantar PostgreSQL con Docker (coincide con .env.example)
docker compose up -d

.venv/bin/python manage.py migrate
.venv/bin/python manage.py compilemessages --ignore=.venv   # traducciones (requiere GNU gettext)
.venv/bin/python manage.py runserver
```

Abre http://localhost:8000, crea una cuenta y luego tu primer proyecto.

Para nombrar al administrador (siempre hay uno solo; el comando se lo quita a los demás):

```bash
.venv/bin/python manage.py setadmin <usuario>
```

Si cambias textos de la interfaz, regenera y traduce el catálogo:

```bash
.venv/bin/python manage.py makemessages -l es --no-wrap --ignore=.venv
# edita locale/es/LC_MESSAGES/django.po y luego:
.venv/bin/python manage.py compilemessages --ignore=.venv
```

Tests (crean una base de datos temporal de PostgreSQL):

```bash
.venv/bin/python manage.py test
```

## Uso desde un frontend

```js
import { createClient } from "http://localhost:8000/sdk/falcondb.js"

const db = createClient("http://localhost:8000", "PROJECT_REF", "ANON_KEY")

// Leer con filtros
const { data, count, error } = await db.from("productos")
  .select("id,nombre,precio")
  .gte("precio", 10)
  .order("precio", { desc: true })
  .limit(20)

// Escribir
await db.from("productos").insert({ nombre: "Café", precio: 2.5 })
await db.from("productos").update(7, { precio: 3 })
await db.from("productos").delete(7)

// Login de usuarios de tu app
await db.auth.signUp({ email, password })
await db.auth.signIn({ email, password })
const { user } = await db.auth.getUser()
db.auth.signOut()
```

Sin SDK:

```bash
curl "http://localhost:8000/api/v1/PROJECT_REF/tables/productos?precio=gte.10&order=precio.desc" \
  -H "apikey: ANON_KEY"
```

### Endpoints

| Método | Ruta | Acción |
|---|---|---|
| GET | `/api/v1/<ref>` | Tablas y columnas visibles |
| GET | `/api/v1/<ref>/tables/<tabla>` | Lista filas → `{data, count}` |
| POST | `/api/v1/<ref>/tables/<tabla>` | Inserta un objeto o una lista |
| GET / PATCH / DELETE | `/api/v1/<ref>/tables/<tabla>/<id>` | Una fila |
| POST | `/api/v1/<ref>/auth/signup` | Registro → `{user, token}` |
| POST | `/api/v1/<ref>/auth/login` | Login → `{user, token}` |
| GET / PATCH | `/api/v1/<ref>/auth/user` | Usuario actual (requiere token) |

Cabeceras: `apikey: <anon|service key>` siempre, y `Authorization: Bearer <token>` para actuar como usuario con sesión.
Filtros: `columna=operador.valor` con `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `ilike`, `is` (`null`/`true`/`false`) e `in` (`in.(a,b)`). Además: `select`, `order`, `limit`, `offset`.

## Arquitectura

```
config/      settings y URLs
core/        home, docs, registro/login, 2FA (totp.py), perfil, admin de usuarios, SDK
locale/      traducción al español (django.po)
projects/    modelos (Project, ProjectTable, ProjectUser), dashboard
  schema.py    motor que crea y consulta las tablas reales (psycopg.sql)
  services.py  operaciones que tocan modelos + DDL en una misma transacción
api/         API REST, claves/tokens, reglas de acceso y CORS
templates/   vistas estilo GitHub
static/      CSS, JS del dashboard y SDK (falcondb.js)
```

- Las tablas de cada proyecto viven en su propio esquema de PostgreSQL; los metadatos (nombre, regla de acceso) en `ProjectTable`. Las columnas se leen directamente del catálogo de PostgreSQL.
- Los nombres de tablas y columnas se validan (`^[a-z_][a-z0-9_]{0,62}$`) y se componen con `psycopg.sql.Identifier`; los valores siempre van como parámetros.
- Los tokens de usuario son firmas de Django (`django.core.signing`) ligadas al proyecto, con caducidad configurable (`FALCONDB_TOKEN_MAX_AGE`).

## Configuración (.env)

| Variable | Por defecto | Descripción |
|---|---|---|
| `SECRET_KEY` | `dev-insecure-change-me` | Clave de Django. **Cámbiala en producción.** |
| `DEBUG` | `true` | |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | |
| `POSTGRES_DB` / `USER` / `PASSWORD` / `HOST` / `PORT` | `falcondatabase` / – / – / `localhost` / `5432` | |
| `FALCONDB_CORS_ORIGINS` | `*` | Orígenes que pueden llamar a la API desde el navegador |
| `FALCONDB_TOKEN_MAX_AGE` | `604800` | Duración de los tokens de usuario (segundos) |
| `FALCONDB_MAX_PAGE_SIZE` | `1000` | Máximo de filas por petición |
| `FALCONDB_CONTACT_NAME` / `FALCONDB_CONTACT_EMAIL` | Marlon Falcon Hernández / mfalconsoft@gmail.com | Contacto que aparece en el pie de página |

## Paleta de colores

| Color | Uso |
|---|---|
| `#ED637D` | Marca, pestaña activa, avatar |
| `#66D7D1` | Botones principales y enlaces (en modo claro los enlaces usan `#117a74` para que el texto tenga suficiente contraste) |
| `#FFF87F` | Avisos y resaltados |
| `#F4F1BB` | Mensajes informativos en modo claro |
| `#EAF2E3` | Cabecera y superficies en modo claro |

Todos los colores están definidos como variables en `static/css/app.css`.

## Contacto

Marlon Falcon Hernández — [mfalconsoft@gmail.com](mailto:mfalconsoft@gmail.com)
