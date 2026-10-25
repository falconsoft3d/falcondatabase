---
title: "Tutorial: trabaja en equipo y sigue tus contribuciones"
date: 2026-10-25
category: tutorial
summary: Comparte un proyecto con otras cuentas como editor o lector, y mira un gráfico al estilo de GitHub con todo lo que cambia.
tags: equipos, compartir, actividad, tutorial
---
Los proyectos no tienen por qué ser cosa de una sola persona. Puedes invitar a otras cuentas de falcondatabase a un proyecto y decidir qué pueden hacer, y un gráfico de contribuciones muestra lo activo que está cada proyecto.

## Comparte un proyecto

1. Abre el proyecto → **Configuración** → **Miembros**.
2. Escribe el **email** de la cuenta de la otra persona y elige un rol.
3. Pulsa **Compartir**.

La persona debe tener ya una cuenta en el servidor. Si no la tiene, pídele que se registre primero (o, si el registro está cerrado, pide al administrador que cree la cuenta).

| Rol | Qué puede hacer |
|---|---|
| **Editor** | Trabajar dentro del proyecto: tablas, filas, estructura, usuarios de la app, analítica, almacenamiento y portal |
| **Lector** | Abrir todas las páginas y leer los datos, pero sin cambiar nada |
| **Dueño** (tú) | Todo, además de Configuración: renombrar, API keys, exportar, miembros y eliminar el proyecto |

El proyecto aparece entonces en **Compartidos contigo** en su dashboard, en su página de **Analítica** y en la extensión de Chrome. Un aviso recuerda a los lectores que su acceso es de solo lectura.

Puedes cambiar el rol de un miembro o quitarlo en **Configuración → Miembros** cuando quieras, y los miembros pueden salir de un proyecto desde su **Resumen**.

## Tu gráfico de contribuciones

El dashboard muestra un gráfico como el de GitHub: un cuadrado por cada día del último año, más oscuro (o más brillante en modo oscuro) cuantos más cambios hubo ese día. Pasa el ratón por un cuadrado para ver el número exacto y la fecha.

Usa el selector sobre el gráfico para ver **todos tus proyectos** o **uno solo**. El **Resumen** de cada proyecto tiene también su propio gráfico.

## Qué cuenta como contribución

Cualquier cambio en un proyecto, venga de donde venga:

- crear o eliminar tablas, agregar o quitar columnas;
- insertar, actualizar o eliminar filas, **desde el dashboard, la API REST o el portal**;
- subir o eliminar archivos y crear buckets;
- agregar usuarios de la app y compartir el proyecto.

Insertar 50 filas en una sola petición cuenta como **una** contribución, como un commit con muchas líneas.

## Actividad reciente

Bajo el gráfico, el **Resumen** de cada proyecto lista los últimos cambios y quién los hizo:

- **ana** insertó filas en `pedidos` (×12) · hace 3 minutos
- **API (service key)** actualizó una fila en `productos` · hace 1 hora
- **eva@ejemplo.com** eliminó una fila de `tareas` · ayer

Los cambios hechos por cuentas del dashboard muestran su usuario. Los de los usuarios de tu app muestran su email, y las llamadas con API keys muestran "API".

## Tu historial ya está ahí

Los proyectos creados antes de esta función recuperan su historial a partir de las fechas ya guardadas (cuándo se crearon las tablas, filas, archivos y usuarios), así tu gráfico no empieza vacío.
