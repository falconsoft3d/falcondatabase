---
title: "falcondatabase 0.6: portales, almacenamiento de archivos y analítica"
date: 2026-10-25
category: news
summary: Convierte proyectos en apps, guarda archivos, mide tus webs y lleva proyectos de un servidor a otro. Aquí está todo lo nuevo de la 0.5 y la 0.6.
tags: versión, anuncio
---
Las dos últimas versiones agregan las piezas más pedidas: un lugar para guardar archivos, una forma de dar acceso a los datos a personas que no programan, y cifras sobre las webs construidas con falcondatabase.

## Versión 0.6

**Portal.** Cualquier proyecto puede convertirse en una app independiente en `/app/<usuario>/<dirección>/`. Sus usuarios inician sesión y ven la lista de tablas que compartes, con búsqueda y formularios generados a partir de las columnas. Cada tabla puede estar oculta, en solo lectura o editable, y las tablas Dueño mantienen privadas las filas de cada usuario. → *Tutorial: convierte un proyecto en una app con el Portal*

**Almacenamiento de archivos.** Buckets públicos y privados, un explorador de archivos en el dashboard, subidas desde tu app con `db.storage.from(bucket).upload()` y enlaces firmados que caducan. → *Tutorial: guarda archivos en buckets, un S3 más simple*

## Versión 0.5

**Analítica web.** Un script de 1 KB sin cookies da a cada proyecto gráficos de sesiones, usuarios y páginas vistas, además de países, fuentes, páginas y dispositivos. La nueva página **Analítica** combina todos tus proyectos. → *Tutorial: analítica web respetuosa con la privacidad para tu sitio*

**Exportar e importar.** Descarga un proyecto en JSON, con o sin datos, y recréalo donde quieras. → *Guía: exporta e importa proyectos en JSON*

**Indicadores en el dashboard.** Diez cifras en la parte superior de tu dashboard: proyectos, tablas, filas, almacenamiento, usuarios de apps, usuarios nuevos y activos, visitantes, páginas vistas y tasa de rebote, con su variación en los últimos 30 días.

**Fotos de perfil**, y una página de **Versiones** enlazada desde el menú. La versión actual también aparece en el pie de página, así siempre sabes qué está funcionando.

## Correcciones

- Abrir **Configuración** ya no salta al campo de contraseña.
- Las fechas ya no se superponen en los gráficos de 30 y 90 días.

## Actualizar

¿Lo alojas tú con Docker? Actualiza con dos comandos. Tus datos y tu configuración se conservan:

```bash
git pull
./install.sh
```

Novedad en la instalación con Docker: un volumen `storage` para los archivos subidos. Inclúyelo en tus copias de seguridad como se explica en `DEPLOY.md`.
