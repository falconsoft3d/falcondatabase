---
title: "Tutorial: analítica web respetuosa con la privacidad para tu sitio"
date: 2026-10-25
category: tutorial
summary: Agrega una etiqueta script a tu web y obtén sesiones, usuarios, páginas vistas, países, fuentes y dispositivos, sin cookies ni avisos.
tags: analítica, privacidad, tutorial
---
Cada proyecto puede medir el tráfico de las webs que lo usan. El script de seguimiento ocupa alrededor de 1 KB, **no usa cookies** y **no guarda direcciones IP**, así que tus visitantes no tienen que aceptar un aviso de cookies por él.

## 1. Activa la analítica

Abre tu proyecto → pestaña **Analítica** → marca **Activar analítica** → **Guardar**.

Opcionalmente rellena **Dominios permitidos** (por ejemplo `ejemplo.com, tienda.ejemplo.com`). Solo se contarán las visitas de esos dominios y sus subdominios, así nadie puede ensuciar tus números copiando el código.

## 2. Agrega el script a tu web

Pega esto en el `<head>` de todas las páginas:

```html
<script defer data-project="PROJECT_REF" src="%BASE_URL%/a.js"></script>
```

La pestaña Analítica muestra el código con tu `PROJECT_REF` real, listo para copiar.

Las apps de una sola página (React, Vue, Svelte…) funcionan: el script también cuenta las navegaciones hechas con `history.pushState` y los botones de atrás/adelante.

## 3. Lee el panel

Elige un periodo (**7, 14, 30 o 90 días**). Cada número se compara con el periodo anterior de la misma duración.

| Indicador | Significado |
|---|---|
| Visitantes | Visitantes únicos por día |
| Sesiones | Visitas; una sesión termina tras 30 minutos sin actividad |
| Páginas vistas | Cada carga de página o navegación |
| Páginas / sesión | Páginas vistas divididas entre sesiones |
| Tasa de rebote | Sesiones con una sola página vista (mejor cuanto más baja) |

Debajo, tres gráficos diarios (sesiones, usuarios, páginas vistas) muestran la tendencia. Pasa el ratón para leer cada día, o abre **Ver como tabla**. Después vienen los desgloses:

- **Países**: de la cabecera de tu CDN (`CF-IPCountry`) si usas una, si no de la zona horaria del navegador, y si no del idioma del navegador.
- **Medios**: Directo, Búsqueda orgánica, Redes sociales, Referencia, Búsqueda de pago, Email…
- **Fuentes**: Google, LinkedIn, github.com, newsletter…
- **Páginas principales**, **dispositivos**, **navegadores** y **sistemas operativos**.

## 4. Mide tus campañas con parámetros UTM

Agrega parámetros UTM a los enlaces que compartas y la sesión tomará de ellos su fuente y su medio:

```
https://ejemplo.com/?utm_source=newsletter&utm_medium=email&utm_campaign=octubre
```

`utm_medium=cpc` aparece como **Búsqueda de pago** y `utm_medium=email` como **Email**.

## 5. Todos tus proyectos a la vez

**Analítica** en el menú principal (`/analytics/`) combina todos los proyectos. Marca los que quieras comparar, o déjalos todos sin marcar para verlo todo, y la lista **Por proyecto** te dice cuál recibe más tráfico.

## Cómo se protege la privacidad

- Sin cookies, sin `localStorage` y sin scripts de huella digital.
- El identificador del visitante es un hash irreversible del día, el proyecto, la IP y el navegador. Cambia cada día, así que no se puede seguir a nadie de un día a otro. Por eso "visitantes" significa visitantes únicos *por día*.
- La ruta de la página se guarda sin los parámetros de la URL.
- Se ignoran los bots y rastreadores.

> **¿Lo alojas tú detrás de un proxy?** Asegúrate de tener `FALCONDB_TRUST_PROXY=true` (automático con `USE_HTTPS=true`). Si no, todas las visitas parecerán venir del proxy.

## Pruébalo con datos de ejemplo

Si tienes tu propio servidor y quieres ver los gráficos antes de instalar el script en ningún sitio:

```bash
python manage.py seed_analytics <usuario>/<slug-del-proyecto> --days 30
```
