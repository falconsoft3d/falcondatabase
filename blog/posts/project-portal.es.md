---
title: "Tutorial: convierte un proyecto en una app con el Portal"
date: 2026-10-25
category: tutorial
summary: Da a tu equipo o a tus clientes su propia dirección donde inician sesión y ven o editan tus tablas, con formularios generados automáticamente.
tags: portal, sin-código, tutorial
---
A veces no necesitas un frontend a medida: necesitas un lugar donde unas pocas personas inicien sesión y gestionen algunas tablas. Eso es el **Portal**: cualquier proyecto puede convertirse en una app independiente con su propia dirección, login, lista de tablas, búsqueda y formularios, sin escribir código.

## 1. Activa el portal

Abre el proyecto → pestaña **Portal**:

1. Marca **Activar portal**.
2. Elige una **dirección**, por ejemplo `inventario` (de 3 a 50 minúsculas, números y guiones).
3. Para cada tabla, elige cómo aparece:

| Modo | En el portal |
|---|---|
| **Oculta** | No se muestra |
| **Solo ver** | Lista, búsqueda y detalle |
| **Ver y editar** | Además crear, editar y eliminar |

4. **Guardar**.

Tu app ya está publicada en:

```
%BASE_URL%/app/<tu-usuario>/inventario/
```

La dirección incluye tu usuario, así que dos personas pueden tener un portal `inventario`.

## 2. Quién puede entrar

Se entra con los **usuarios del proyecto** (pestaña **Autenticación**): créalos ahí con un email y una contraseña. Si **Permitir registro público** está activado, las personas también pueden crear su propia cuenta desde la página de acceso del portal.

La sesión del portal es independiente de tu cuenta del dashboard: entrar a un portal nunca da acceso a tus proyectos ni a tus claves.

## 3. Qué ven tus usuarios

- Una barra lateral con las tablas que compartiste.
- En cada tabla: un cuadro de **búsqueda** (busca en todas las columnas), columnas ordenables y 25 filas por página.
- En las tablas **Ver y editar**: un botón **Nuevo** y un botón **Editar** en cada fila. Los formularios se generan a partir de las columnas: campos de texto y números, selectores de fecha, selectores verdadero/falso y un editor JSON. Los campos obligatorios están marcados.
- La validación viene de la base de datos: una columna obligatoria vacía o un duplicado en una columna única muestran un error claro.

## 4. Filas privadas por usuario

Si una tabla usa la regla de acceso **Dueño**, cada usuario del portal solo ve y edita **sus propias filas**, y las nuevas se le asignan automáticamente. Úsalo para solicitudes, pedidos, partes de horas… todo lo personal.

## 5. Portales públicos

Marca **Portal público** para que cualquiera pueda ver las tablas **Solo ver** sin iniciar sesión, por ejemplo un catálogo público o una lista de eventos. Incluso en un portal público:

- crear, editar y eliminar siempre requieren iniciar sesión;
- las tablas **Dueño** siempre requieren iniciar sesión.

## Ideas

- **Inventario del equipo**: `articulos` en *Ver y editar*, `proveedores` en *Solo ver*.
- **Solicitudes de clientes**: una tabla `solicitudes` con la regla Dueño, para que cada cliente vea solo las suyas.
- **Directorio público**: un portal público con una tabla `miembros` en *Solo ver*.

¿Necesitas más control sobre el diseño? Construye tu propio frontend con el SDK. El portal y tu app a medida pueden usar el mismo proyecto a la vez.
