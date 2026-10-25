"""Release history shown at /changelog/. The newest release goes first and sets VERSION.

Add an entry here with every new feature or fix (in English and Spanish).
Change kinds: "added", "improved", "fixed".
"""

RELEASES = [
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
