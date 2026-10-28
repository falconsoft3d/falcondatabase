"""Release history shown at /changelog/. The newest release goes first and sets VERSION.

Add an entry here with every new feature or fix (in English and Spanish).
Change kinds: "added", "improved", "fixed".
"""

RELEASES = [
    {
        "version": "0.10.3",
        "date": "2026-10-28",
        "title": {"en": "MCP on the home page", "es": "MCP en la página de inicio"},
        "changes": [
            ("improved", "The home page explains the MCP server: the URL to copy, the steps to add it to Claude as a connector, the Claude Code command, how other clients connect and every tool the AI can use.",
                         "La página de inicio explica el servidor MCP: la URL para copiar, los pasos para añadirlo a Claude como conector, el comando de Claude Code, cómo se conectan otros clientes y todas las herramientas que puede usar la IA."),
        ],
    },
    {
        "version": "0.10.2",
        "date": "2026-10-28",
        "title": {"en": "Claude connector: always HTTPS", "es": "Conector de Claude: siempre HTTPS"},
        "changes": [
            ("fixed", "The OAuth and MCP addresses of a server with a domain name are always announced with https://, even if the proxy in front does not send X-Forwarded-Proto. Adding the connector in Claude no longer fails at the registration step. Local addresses and IPs are unchanged.",
                      "Las direcciones OAuth y MCP de un servidor con dominio se anuncian siempre con https://, aunque el proxy de delante no envíe X-Forwarded-Proto. Añadir el conector en Claude ya no falla en el paso de registro. Las direcciones locales y las IP no cambian."),
            ("fixed", "The connection guide shows the MCP URL with https:// on those servers, ready to paste into Claude.",
                      "La guía de conexión muestra la URL del MCP con https:// en esos servidores, lista para pegar en Claude."),
        ],
    },
    {
        "version": "0.10.1",
        "date": "2026-10-28",
        "title": {"en": "Claude connector behind nginx", "es": "Conector de Claude detrás de nginx"},
        "changes": [
            ("fixed", "Adding the Claude connector failed (\"could not register with the sign-in service\") on servers behind their own nginx: the OAuth addresses were announced with http://. With FALCONDB_TRUST_PROXY=true the X-Forwarded-Proto header of the proxy is now trusted and they use https://.",
                      "Añadir el conector de Claude fallaba (\"no se ha podido completar el registro en el servicio de inicio de sesión\") en servidores detrás de su propio nginx: las direcciones OAuth se anunciaban con http://. Con FALCONDB_TRUST_PROXY=true ahora se confía en la cabecera X-Forwarded-Proto del proxy y usan https://."),
        ],
    },
    {
        "version": "0.10.0",
        "date": "2026-10-28",
        "title": {"en": "Connect Claude with one click", "es": "Conecta Claude con un clic"},
        "changes": [
            ("added", "Add falcondatabase to Claude (claude.ai, Desktop or mobile) as a custom connector: paste the MCP URL, press Connect, sign in and choose which projects it may reach and whether it can write. No token to copy.",
                      "Añade falcondatabase a Claude (claude.ai, Desktop o el móvil) como conector personalizado: pega la URL del MCP, pulsa Conectar, inicia sesión y elige a qué proyectos accede y si puede escribir. Sin copiar ningún token."),
            ("added", "OAuth 2.1 for MCP clients: discovery, dynamic client registration, PKCE, renewable access and revocation. Claude Code connects the same way with /mcp → Authenticate.",
                      "OAuth 2.1 para clientes MCP: descubrimiento, registro dinámico de clientes, PKCE, acceso renovable y revocación. Claude Code se conecta igual con /mcp → Authenticate."),
            ("improved", "Connected assistants appear in Settings → AI access as \"connector\" and are revoked there like any token. The connection guide starts with the \"Connect with Claude\" button.",
                         "Los asistentes conectados aparecen en Ajustes → Acceso IA como \"conector\" y se revocan allí como cualquier token. La guía de conexión empieza con el botón \"Conectar con Claude\"."),
            ("added", "Automatic deploy: every push to main runs the tests and, if they pass, updates the server over SSH with the new deploy.sh (database backup, git pull and ./install.sh). Set it up in DEPLOY.md.",
                      "Despliegue automático: cada push a main pasa los tests y, si van bien, actualiza el servidor por SSH con el nuevo deploy.sh (copia de la base de datos, git pull y ./install.sh). Se configura siguiendo DEPLOY.md."),
        ],
    },
    {
        "version": "0.9.0",
        "date": "2026-10-27",
        "title": {"en": "Uptime monitoring", "es": "Monitor de uptime"},
        "changes": [
            ("added", "\"Uptime\" tab in every project: add the address of a website and it is requested every 1, 5, 10, 15, 30 or 60 minutes (5 by default). A failed request is retried once before it counts as down.",
                      "Pestaña \"Uptime\" en cada proyecto: añade la dirección de un sitio web y se consulta cada 1, 5, 10, 15, 30 o 60 minutos (5 por defecto). Una petición fallida se reintenta una vez antes de contar como caída."),
            ("added", "History and charts for each monitor: uptime per day for the last 90 days, response time, uptime percentage, incidents with their duration and the latest checks, for 24 hours, 7, 30 or 90 days.",
                      "Historial y gráficas de cada monitor: disponibilidad por día de los últimos 90 días, tiempo de respuesta, porcentaje de uptime, caídas con su duración y las últimas comprobaciones, para 24 horas, 7, 30 o 90 días."),
            ("added", "Alerts when a site goes down and when it comes back: an email to the project owner (if enabled on the monitor) and an optional webhook for Slack, Discord or any service.",
                      "Avisos cuando un sitio se cae y cuando vuelve: un email al dueño del proyecto (si está activado en el monitor) y un webhook opcional para Slack, Discord o cualquier servicio."),
            ("added", "/uptime/ page with every monitor of your projects, and one click to monitor the domains of your analytics.",
                      "Página /uptime/ con todos los monitores de tus proyectos y un clic para monitorizar los dominios de tu analítica."),
            ("added", "\"Check all now\" button in /uptime/ to request every website at once, without waiting for its turn.",
                      "Botón \"Comprobar todos ahora\" en /uptime/ para consultar todos los sitios a la vez, sin esperar a su turno."),
            ("added", "New \"uptime\" service in Docker (manage.py uptime_worker) and SMTP settings in .env for the emails.",
                      "Nuevo servicio \"uptime\" en Docker (manage.py uptime_worker) y ajustes SMTP en el .env para los emails."),
        ],
    },
    {
        "version": "0.8.0",
        "date": "2026-10-27",
        "title": {"en": "Manage it with AI", "es": "Gestiónalo con IA"},
        "changes": [
            ("added", "AI tokens (Settings → AI access): give Claude, Cursor or any assistant a token and it can create and edit tables, columns, data and the users of your apps. A token can be limited to one project or be read-only, and is revoked in one click.",
                      "Tokens de IA (Ajustes → Acceso IA): dale un token a Claude, Cursor o cualquier asistente y podrá crear y editar tablas, columnas, datos y los usuarios de tus apps. Un token puede limitarse a un proyecto o ser de solo lectura, y se revoca con un clic."),
            ("added", "MCP server at /api/ai/mcp and the same tools over HTTP at /api/ai/tools/<tool>.",
                      "Servidor MCP en /api/ai/mcp y las mismas herramientas por HTTP en /api/ai/tools/<herramienta>."),
            ("added", "\"AI\" tab in every project with the connection guide already filled in with the server, the project and a token created right there.",
                      "Pestaña \"IA\" en cada proyecto con la guía de conexión ya rellenada con el servidor, el proyecto y un token creado allí mismo."),
            ("added", "\"Manage it with AI\" page, linked from the home page, explaining how it works.",
                      "Página \"Gestiónalo con IA\", enlazada desde el inicio, que explica cómo funciona."),
        ],
    },
    {
        "version": "0.7.6",
        "date": "2026-10-26",
        "title": {"en": "Analytics: Today period", "es": "Analítica: periodo Hoy"},
        "changes": [
            ("added", "\"Today\" period in the analytics and the Chrome extension, with an hourly chart and a comparison with yesterday. It is now the default period.",
                      "Periodo \"Hoy\" en la analítica y en la extensión de Chrome, con gráfica por horas y comparación con ayer. Ahora es el periodo por defecto."),
        ],
    },
    {
        "version": "0.7.5",
        "date": "2026-10-25",
        "title": {"en": "Extension: refresh button", "es": "Extensión: botón de actualizar"},
        "changes": [
            ("added", "Refresh button in the Chrome extension to reload the statistics without closing it.",
                      "Botón de actualizar en la extensión de Chrome para recargar las estadísticas sin cerrarla."),
            ("fixed", "Changing the project or the period in the extension always shows that selection's KPIs: late answers are ignored and a failed load no longer leaves the previous numbers.",
                      "Al cambiar de proyecto o de periodo en la extensión se ven siempre los KPI de esa selección: se ignoran respuestas tardías y una carga fallida ya no deja los números anteriores."),
        ],
    },
    {
        "version": "0.7.4",
        "date": "2026-10-25",
        "title": {"en": "Installer: server address", "es": "Instalador: dirección del servidor"},
        "changes": [
            ("fixed", "\"Bad Request (400)\" when opening an install by its IP: the installer now suggests the server's IP instead of localhost and accepts it too.",
                      "\"Bad Request (400)\" al abrir una instalación por su IP: el instalador ahora propone la IP del servidor en lugar de localhost y también la acepta."),
            ("fixed", "\"CSRF verification failed\" when the site is opened through https:// and the proxy doesn't tell the app: your own domains are now trusted with https.",
                      "\"La verificación CSRF ha fallado\" al abrir la web por https:// cuando el proxy no se lo indica a la app: ahora tus propios dominios se aceptan con https."),
            ("improved", "A rejected form shows a clear page with the reason, instead of Django's generic error.",
                         "Un formulario rechazado muestra una página clara con el motivo, en lugar del error genérico de Django."),
            ("improved", "Running ./install.sh again on an install left on localhost asks for the address and fixes .env.",
                         "Volver a ejecutar ./install.sh en una instalación que quedó en localhost pide la dirección y corrige el .env."),
            ("added", "Step-by-step guide in Spanish to update the server: docs/actualizar-servidor.md.",
                      "Guía paso a paso en español para actualizar el servidor: docs/actualizar-servidor.md."),
            ("added", "Change the address or switch to HTTPS with one command: FALCONDB_DOMAIN=… FALCONDB_HTTPS=yes ./install.sh --yes.",
                      "Cambia la dirección o pasa a HTTPS con un comando: FALCONDB_DOMAIN=… FALCONDB_HTTPS=yes ./install.sh --yes."),
        ],
    },
    {
        "version": "0.7.3",
        "date": "2026-10-25",
        "title": {"en": "Server setup and updates guide", "es": "Guía de preparación y actualización del servidor"},
        "changes": [
            ("added", "DEPLOY.md: preparing a fresh server (updates, user, firewall, swap) and installing Docker step by step.",
                      "DEPLOY.md: preparar un servidor nuevo (actualizaciones, usuario, cortafuegos, swap) e instalar Docker paso a paso."),
            ("added", "DEPLOY.md: routine to keep the server, Docker, falcondatabase and its images up to date.",
                      "DEPLOY.md: rutina para mantener al día el servidor, Docker, falcondatabase y sus imágenes."),
            ("improved", "The installer also downloads the latest PostgreSQL and Caddy images when updating.",
                         "El instalador también descarga las últimas imágenes de PostgreSQL y Caddy al actualizar."),
        ],
    },
    {
        "version": "0.7.2",
        "date": "2026-10-25",
        "title": {"en": "Animated home page", "es": "Inicio animado"},
        "changes": [
            ("added", "Animated triangle mesh in the home page header that opens around the mouse.",
                      "Malla de triángulos animada en la cabecera del inicio que se abre alrededor del ratón."),
            ("improved", "README reorganized by topic, with new screenshots.", "README reorganizado por temas, con capturas nuevas."),
        ],
    },
    {
        "version": "0.7.1",
        "date": "2026-10-25",
        "title": {"en": "Blog search and categories", "es": "Búsqueda y categorías en el blog"},
        "changes": [
            ("added", "Search the blog: titles, summaries, tags and text, ignoring accents and capital letters.",
                      "Busca en el blog: títulos, resúmenes, etiquetas y texto, sin importar tildes ni mayúsculas."),
            ("added", "Blog categories with their number of articles, and clickable topics (tags) to filter.",
                      "Categorías del blog con su número de artículos, y temas (etiquetas) clicables para filtrar."),
            ("improved", "Link to the extension's installation guide on the home page and the extension page.",
                         "Enlace a la guía de instalación de la extensión en el inicio y en la página de la extensión."),
        ],
    },
    {
        "version": "0.7.0",
        "date": "2026-10-25",
        "title": {"en": "Teams, contributions and the Chrome extension", "es": "Equipos, contribuciones y la extensión de Chrome"},
        "changes": [
            ("added", "Share a project with other accounts by email, as editor or viewer. Shared projects appear in the dashboard and in analytics.",
                      "Comparte un proyecto con otras cuentas por email, como editor o lector. Los proyectos compartidos aparecen en el dashboard y en la analítica."),
            ("added", "Contribution graph of the last year, like GitHub's: for all your projects on the dashboard and for each project in its overview.",
                      "Gráfico de contribuciones del último año, como el de GitHub: de todos tus proyectos en el dashboard y de cada proyecto en su resumen."),
            ("added", "Recent activity of each project: who created, changed or deleted tables, rows, files and members.",
                      "Actividad reciente de cada proyecto: quién creó, cambió o eliminó tablas, filas, archivos y miembros."),
            ("added", "Chrome extension with the statistics of your projects and today's visits on its icon, downloadable from the home page.",
                      "Extensión de Chrome con las estadísticas de tus proyectos y las visitas de hoy en su icono, descargable desde el inicio."),
            ("added", "Account API (/api/account/) used by the extension, with two-step authentication support.",
                      "API de cuenta (/api/account/) que usa la extensión, compatible con la autenticación en dos pasos."),
        ],
    },
    {
        "version": "0.6.1",
        "date": "2026-10-25",
        "title": {"en": "Site analytics and documentation", "es": "Analítica del sitio y documentación"},
        "changes": [
            ("added", "The admin can measure visits to this site's public pages and see them in Analytics.",
                      "El admin puede medir las visitas a las páginas públicas de este sitio y verlas en Analítica."),
            ("added", "Five new blog articles: web analytics, the portal, file storage, export/import and the 0.6 release.",
                      "Cinco artículos nuevos en el blog: analítica web, el portal, almacenamiento de archivos, exportar/importar y la versión 0.6."),
            ("improved", "The documentation covers storage, web analytics and the portal.",
                         "La documentación cubre el almacenamiento, la analítica web y el portal."),
            ("fixed", "Selecting a single project in the combined analytics page now works.",
                      "Seleccionar un único proyecto en la página de analítica combinada ahora funciona."),
            ("improved", "File pickers use the site's language and style instead of the browser's.",
                         "Los selectores de archivos usan el idioma y el estilo del sitio en lugar de los del navegador."),
            ("improved", "Screenshots in the README.", "Capturas de pantalla en el README."),
        ],
    },
    {
        "version": "0.6.0",
        "date": "2026-10-25",
        "title": {"en": "Portals and file storage", "es": "Portales y almacenamiento de archivos"},
        "changes": [
            ("added", "Project portal: turn a project into a standalone app at /app/<user>/<address>/ where its users "
                      "sign in and view or edit the tables you choose, with automatic forms and search.",
                      "Portal de proyecto: convierte un proyecto en una app independiente en /app/<usuario>/<dirección>/ "
                      "donde sus usuarios inician sesión y ven o editan las tablas que elijas, con formularios automáticos y búsqueda."),
            ("added", "File storage per project: public and private buckets, a file browser, uploads from your app, "
                      "and signed links that expire.",
                      "Almacenamiento de archivos por proyecto: buckets públicos y privados, explorador de archivos, "
                      "subidas desde tu app y enlaces firmados que caducan."),
            ("added", "Storage in the JavaScript SDK: db.storage.from(bucket).upload, list, remove, getPublicUrl and createSignedUrl.",
                      "Almacenamiento en el SDK de JavaScript: db.storage.from(bucket).upload, list, remove, getPublicUrl y createSignedUrl."),
            ("improved", "Bucket definitions and portal settings are included in the JSON export.",
                         "La exportación JSON incluye los buckets y la configuración del portal."),
            ("fixed", "Opening Settings no longer scrolls the page down to the password field.",
                      "Abrir Configuración ya no desplaza la página hasta el campo de contraseña."),
            ("fixed", "Date labels no longer overlap on 30- and 90-day analytics charts.",
                      "Las fechas ya no se superponen en los gráficos de analítica de 30 y 90 días."),
        ],
    },
    {
        "version": "0.5.0",
        "date": "2026-10-25",
        "title": {"en": "Analytics and data portability", "es": "Analítica y portabilidad de datos"},
        "changes": [
            ("added", "Web analytics per project: a cookie-free tracking script and charts for sessions, users, "
                      "pageviews, countries, mediums, sources, pages, devices and browsers.",
                      "Analítica web por proyecto: un script de seguimiento sin cookies y gráficos de sesiones, "
                      "usuarios, páginas vistas, países, medios, fuentes, páginas, dispositivos y navegadores."),
            ("added", "Combined analytics page for all your projects or a selection of them.",
                      "Página de analítica combinada para todos tus proyectos o una selección."),
            ("added", "Export a project to JSON (structure, optionally with data) and import it as a new project.",
                      "Exporta un proyecto a JSON (estructura y, opcionalmente, datos) e impórtalo como un proyecto nuevo."),
            ("added", "Profile picture.", "Foto de perfil."),
            ("added", "Ten key indicators at the top of the dashboard.", "Diez indicadores clave en la parte superior del dashboard."),
            ("added", "This versions page and the version number in the footer.",
                      "Esta página de versiones y el número de versión en el pie de página."),
        ],
    },
    {
        "version": "0.4.0",
        "date": "2026-10-25",
        "title": {"en": "Deployment, blog and cookies", "es": "Despliegue, blog y cookies"},
        "changes": [
            ("added", "Step-by-step Docker installer (install.sh) with optional automatic HTTPS, and a deployment guide.",
                      "Instalador paso a paso con Docker (install.sh) con HTTPS automático opcional, y guía de despliegue."),
            ("added", "Blog with 10 articles and tutorials in English and Spanish.",
                      "Blog con 10 artículos y tutoriales en inglés y español."),
            ("added", "Cookie consent banner and cookie policy page.", "Aviso de consentimiento de cookies y página de política de cookies."),
            ("added", "The admin can reset a user's password from the Users page.",
                      "El admin puede restablecer la contraseña de un usuario desde la página Usuarios."),
            ("improved", "Home link in the main menu.", "Enlace a Inicio en el menú principal."),
            ("improved", "README and deployment documentation in English.", "README y documentación de despliegue en inglés."),
        ],
    },
    {
        "version": "0.3.0",
        "date": "2026-10-25",
        "title": {"en": "Languages, themes and security", "es": "Idiomas, temas y seguridad"},
        "changes": [
            ("added", "Interface in English and Spanish, with a language selector in the header and in the profile.",
                      "Interfaz en inglés y español, con selector de idioma en la cabecera y en el perfil."),
            ("added", "Light and dark mode with the new color palette.", "Modo claro y oscuro con la nueva paleta de colores."),
            ("added", "Two-step authentication (TOTP) with recovery codes.", "Autenticación en dos pasos (TOTP) con códigos de recuperación."),
            ("added", "Contact details in the footer.", "Datos de contacto en el pie de página."),
        ],
    },
    {
        "version": "0.2.0",
        "date": "2026-10-25",
        "title": {"en": "Accounts and administration", "es": "Cuentas y administración"},
        "changes": [
            ("added", "Change your password from your profile.", "Cambia tu contraseña desde tu perfil."),
            ("added", "A single admin with a Users page to see and create accounts.",
                      "Un único admin con una página Usuarios para ver y crear cuentas."),
            ("added", "Switch to disable public sign up.", "Opción para desactivar el registro público."),
        ],
    },
    {
        "version": "0.1.0",
        "date": "2026-10-25",
        "title": {"en": "First version", "es": "Primera versión"},
        "changes": [
            ("added", "Home page, dashboard and GitHub-style interface.", "Página de inicio, dashboard e interfaz estilo GitHub."),
            ("added", "Projects with their own PostgreSQL schema, API URL and anon/service keys.",
                      "Proyectos con su propio esquema de PostgreSQL, URL de API y claves anon/service."),
            ("added", "Real PostgreSQL tables with typed columns, a data editor and column management.",
                      "Tablas reales de PostgreSQL con columnas tipadas, editor de datos y gestión de columnas."),
            ("added", "REST API with filters, ordering, pagination and CORS.", "API REST con filtros, orden, paginación y CORS."),
            ("added", "JavaScript SDK (falcondb.js) with no dependencies.", "SDK de JavaScript (falcondb.js) sin dependencias."),
            ("added", "Login for your apps' users and access rules per table.",
                      "Login para los usuarios de tus apps y reglas de acceso por tabla."),
        ],
    },
]

VERSION = RELEASES[0]["version"]


def releases(lang):
    """Releases with texts in ``lang`` ("es" or anything else for English)."""
    spanish = lang == "es"
    return [
        {
            "version": release["version"],
            "date": release["date"],
            "title": release["title"]["es" if spanish else "en"],
            "changes": [{"kind": kind, "text": es if spanish else en} for kind, en, es in release["changes"]],
        }
        for release in RELEASES
    ]
