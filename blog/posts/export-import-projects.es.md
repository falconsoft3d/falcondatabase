---
title: "Guía: exporta e importa proyectos en JSON"
date: 2026-10-25
category: guide
summary: Copia la estructura de un proyecto, y si quieres sus datos, a un archivo. Úsalo como plantilla, llévalo a otro servidor o crea un entorno nuevo.
tags: json, exportar, importar, migración
---
Cada proyecto puede guardarse como un único archivo JSON y recrearse a partir de él, en el mismo servidor o en otro. Es la forma más rápida de reutilizar una estructura, compartir una plantilla o montar una copia de pruebas.

## Exportar

Abre el proyecto → **Configuración** → **Exportar**:

- **Exportar estructura**: configuración del proyecto, tablas, columnas, valores por defecto, restricciones, reglas de acceso y modos del portal, además de los buckets.
- **Exportar estructura y datos**: lo mismo, más todas las filas de todas las tablas.

El archivo se ve así:

```json
{
  "format": "falcondatabase",
  "version": 1,
  "project": { "name": "Tienda", "description": "", "auth_enabled": true, "storage_enabled": true },
  "tables": [
    {
      "name": "productos",
      "access": "public_read",
      "portal_mode": "view",
      "columns": [
        { "name": "nombre", "type": "text", "required": true, "unique": true, "default": null },
        { "name": "precio", "type": "decimal", "required": false, "unique": false, "default": "0" },
        { "name": "codigo", "type": "uuid", "required": false, "unique": false, "default": "uuid()" }
      ],
      "rows": [{ "id": 1, "created_at": "2026-10-25T10:00:00Z", "nombre": "Café", "precio": "12.50" }]
    }
  ],
  "buckets": [{ "name": "imagenes", "public": true }]
}
```

## Qué no se exporta

| No se incluye | Por qué |
|---|---|
| Los usuarios de tu app | Contienen hashes de contraseñas |
| Los archivos del Almacenamiento | Pueden ser grandes; respáldalos con el servidor |
| La analítica | Pertenece al proyecto original |
| La dirección del portal y las API keys | Deben ser únicas; la copia recibe otras nuevas |

## Importar

Ve a **Nuevo proyecto** → **O importa un proyecto desde JSON**, elige el archivo y, opcionalmente, un nombre nuevo.

- Todo se crea en **una sola transacción**: si falla cualquier tabla, columna o fila, no se crea nada y ves el motivo.
- Los ids de las filas se conservan, y las filas nuevas continúan después del mayor.
- Se copia la configuración (login, registro, analítica, almacenamiento, portal público), pero el portal empieza **desactivado** hasta que elijas su dirección.
- En las tablas con la regla Dueño, las filas pierden su dueño, porque los usuarios no se copian.

El archivo puede pesar como máximo 20 MB. Para bases de datos más grandes, usa las copias de PostgreSQL que se explican en el tutorial de Docker.

## Casos de uso

- **Plantillas**: guarda una estructura de "CRM" o "inventario" y crea un proyecto nuevo con ella en segundos.
- **Pruebas**: exporta *estructura y datos*, impórtalo en un servidor de pruebas y ensaya ahí tus cambios.
- **Cambio de servidor**: exporta cada proyecto, instala falcondatabase en el servidor nuevo, impórtalos y copia los archivos de tus buckets.

El formato es JSON normal, así que también puedes generarlo desde un script para crear proyectos automáticamente.
