---
title: "Tutorial: protege tu cuenta con la autenticación en dos pasos"
date: 2026-10-18
category: tutorial
summary: Agrega un segundo paso al login del dashboard con una app de autenticación y guarda tus códigos de recuperación.
tags: seguridad, 2fa, cuenta
---
Tu cuenta de falcondatabase controla todos tus proyectos, claves y tablas. Una contraseña filtrada no debería bastar para entrar. La autenticación en dos pasos (2FA) agrega un código de 6 dígitos de tu teléfono que cambia cada 30 segundos.

## Qué necesitas

Cualquier app compatible con códigos TOTP: Google Authenticator, Microsoft Authenticator, Authy, 1Password, Bitwarden, Proton Pass…

## 1. Actívala

1. Abre el menú del avatar → **Configuración** (o ve a %BASE_URL%/settings/).
2. En **Autenticación en dos pasos** pulsa **Activar autenticación en dos pasos**.
3. Escanea el código QR con tu app. Si no puedes escanearlo, escribe la clave que aparece al lado.
4. Escribe el código de 6 dígitos que muestra la app y pulsa **Verificar y activar**.

## 2. Guarda tus códigos de recuperación

Justo después de activarla verás **8 códigos de recuperación** como `3fa9c1-07be42`.

- Cada uno te permite entrar **una vez** si no tienes tu teléfono.
- Se muestran **solo esta vez**. Cópialos en tu gestor de contraseñas o imprímelos.
- Cuando te queden dos o menos, falcondatabase te recordará generar nuevos.

## 3. Cómo entras a partir de ahora

1. Escribe tu usuario (o email) y contraseña como siempre.
2. Se te pedirá el **código de autenticación**. Escribe el código actual de tu app, o un código de recuperación.

Por tu seguridad:

- Cada código funciona una sola vez.
- Tras **5 códigos incorrectos** tienes que empezar de nuevo con tu contraseña.
- El paso de verificación caduca a los 5 minutos.

## Gestiónala

En **Configuración → Autenticación en dos pasos**, después de confirmar tu contraseña, puedes:

- **Nuevos códigos de recuperación** — invalida los anteriores y muestra 8 códigos nuevos.
- **Desactivar** — quita el segundo paso.

## ¿Perdiste tu teléfono y tus códigos?

Pide ayuda al administrador. En la página **Usuarios** puede restablecer la autenticación en dos pasos de tu cuenta. Entonces entrarás solo con tu contraseña y podrás activarla de nuevo con tu nuevo teléfono.

## Para administradores

- La página **Usuarios** muestra qué cuentas tienen el 2FA activado.
- Anima a todos los que tengan acceso a proyectos importantes a activarlo, empezando por tu propia cuenta de admin.
