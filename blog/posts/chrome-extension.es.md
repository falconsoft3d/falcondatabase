---
title: "Tutorial: la extensión de Chrome, tus estadísticas a un clic"
date: 2026-10-25
category: tutorial
summary: Instala la extensión de falcondatabase, inicia sesión una vez y consulta las visitas de tus proyectos desde la barra del navegador.
tags: chrome, extensión, analítica, tutorial
---
La extensión de falcondatabase pone la analítica de tus proyectos en la barra del navegador: sin abrir pestañas ni navegar por el dashboard. Su icono muestra incluso cuántas páginas vistas tuvieron hoy tus sitios.

## Qué muestra

- **Cuatro indicadores clave**: visitantes, sesiones, páginas vistas y tasa de rebote, cada uno comparado con el periodo anterior.
- **Un gráfico diario** de páginas vistas. Pasa el ratón por encima para leer cualquier día.
- **Páginas, fuentes y países principales**.
- **Filtros**: todos tus proyectos o uno solo, y los últimos 7, 14, 30 o 90 días.
- **Un número en el icono** con las páginas vistas de hoy, que se actualiza cada 30 minutos.
- Un enlace a la analítica completa del dashboard.

Incluye los proyectos que otras personas compartieron contigo, y está disponible en español e inglés, en modo claro y oscuro.

## Cómo instalarla

La extensión aún no está en la Chrome Web Store, así que Chrome la instala en **modo de desarrollador**. Lleva un minuto:

1. En la página de inicio de tu servidor, pulsa **Obtener la extensión de Chrome**, o ve a %BASE_URL%/extension/.
2. Pulsa **Descargar la extensión**. El zip viene **configurado para tu servidor**, así que no tendrás que escribir su dirección.
3. **Descomprímelo**. Obtendrás una carpeta llamada `falcondatabase-extension`. Guárdala en un sitio fijo (por ejemplo, en Documentos): Chrome carga la extensión desde ahí.
4. Escribe `chrome://extensions` en la barra de direcciones y activa el **Modo de desarrollador** (arriba a la derecha).
5. Pulsa **Cargar descomprimida** y elige la carpeta `falcondatabase-extension`.
6. Pulsa el icono del puzle en la barra y **fija** falcondatabase para que siempre esté visible.

También funciona en Edge, Brave, Opera y otros navegadores Chromium (`edge://extensions`, `brave://extensions`…).

## Inicia sesión

Pulsa el icono y escribe tu **usuario o email** y tu **contraseña** de falcondatabase.

- Si tienes la **autenticación en dos pasos**, la extensión te pide el código de 6 dígitos de tu app, igual que la web.
- La primera vez, Chrome puede pedir permiso para conectarse a tu servidor: acéptalo.
- La sesión dura **30 días**. Cambiar tu contraseña cierra la sesión de la extensión en todas partes.
- **Cerrar sesión** borra la sesión del navegador.

## Cómo funciona

La extensión solo habla con **tu** servidor, nunca con terceros:

1. Al iniciar sesión llama a `POST /api/account/token` y guarda el token que recibe en el almacenamiento local de Chrome.
2. Cada vez que la abres, llama a `GET /api/account/analytics` con ese token y dibuja los números.
3. Un proceso en segundo plano repite la llamada cada 30 minutos para actualizar el número del icono.

El token solo da acceso a tu analítica, a nada más. El código de la extensión está en la carpeta `extension/` del repositorio (Manifest V3), por si quieres revisarlo o cambiarlo.

## Actualizarla

Cuando haya una versión nueva, descarga el zip de nuevo, reemplaza la carpeta y pulsa la flecha de **recargar** de la extensión en `chrome://extensions`. Sigues con la sesión iniciada.

## Solución de problemas

| Problema | Solución |
|---|---|
| "Token inválido o expirado" | Inicia sesión de nuevo (pasa a los 30 días o tras cambiar tu contraseña) |
| "La extensión necesita permiso…" | Acepta el aviso de permisos, o quita la extensión y cárgala de nuevo |
| Todos los números están a cero | Activa la **Analítica** en tus proyectos y agrega el script a tus webs |
| El icono muestra "!" | La sesión caducó: abre la extensión e inicia sesión |
