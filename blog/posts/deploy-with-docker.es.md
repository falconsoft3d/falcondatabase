---
title: "Tutorial: despliega falcondatabase con Docker en 10 minutos"
date: 2026-10-25
category: tutorial
summary: De un servidor Linux vacío a tu propia instancia con HTTPS, usando el script de instalación paso a paso.
tags: docker, despliegue, https, devops
---
falcondatabase incluye una configuración de Docker y un instalador que hace unas pocas preguntas y se encarga del resto: genera los secretos, construye la imagen, arranca PostgreSQL y la app, ejecuta las migraciones y crea tu cuenta de administrador.

## Qué necesitas

- Un servidor Linux (Ubuntu 22.04/24.04, Debian 12…) con al menos 1 GB de RAM.
- **Docker** con el plugin **Compose**.
- Para HTTPS: un dominio (por ejemplo `db.ejemplo.com`) cuyo **registro A** apunte al servidor, y los puertos **80** y **443** abiertos.

En un servidor nuevo, primero actualiza el sistema y abre el cortafuegos:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git curl ufw unattended-upgrades
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
```

Después instala Docker con el script oficial y compruébalo:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # luego cierra sesión y vuelve a entrar
docker compose version
docker run --rm hello-world
```

DEPLOY.md explica cada paso, además de la instalación desde el repositorio apt oficial, el swap para servidores pequeños y un usuario que no sea root.

## 1. Descarga el código

```bash
git clone https://github.com/falconsoft3d/falcondatabase.git
cd falcondatabase
```

## 2. Ejecuta el instalador

```bash
./install.sh
```

Recorre seis pasos:

1. **Comprobación de requisitos** — Docker, Compose, el servicio de Docker y `curl`.
2. **Configuración** — te pregunta:
    - el dominio o IP del servidor,
    - si quieres **HTTPS automático** (solo se ofrece con dominios reales),
    - el puerto HTTP (8000 por defecto, cuando no hay HTTPS),
    - el idioma por defecto (`en` o `es`),
    - la **cuenta de administrador**: usuario, email y contraseña (déjala vacía para generar una segura),
    - el nombre y email de contacto del pie de página.

    Todo se guarda en `.env` con valores aleatorios para `SECRET_KEY` y la contraseña de la base de datos.
3. **Construcción de la imagen** — Python, dependencias, traducciones y archivos estáticos.
4. **Arranque de los contenedores** — `db` (PostgreSQL 16), `web` (Gunicorn, con un volumen `storage` para los archivos subidos) y, con HTTPS, `caddy`.
5. **Espera a la aplicación** — las migraciones se aplican solas y el script consulta `/healthz`.
6. **Cuenta de administrador** — crea tu usuario admin y lo deja como único administrador.

Al final verás algo como:

```
falcondatabase is ready!

  Open:            https://db.ejemplo.com
  Admin user:      admin-user
  Admin password:  Xk3…  (shown only now — change it in Settings)
```

## 3. Primeros pasos tras instalar

1. Inicia sesión y cambia la contraseña si se generó (**Configuración → Cambiar contraseña**).
2. Activa la **autenticación en dos pasos** en tu cuenta de admin.
3. Decide si cualquiera puede registrarse: **Usuarios → Registro**.

## HTTPS explicado

Con HTTPS activado, el instalador copia `docker-compose.https.yml` a `docker-compose.override.yml`, que Docker Compose carga automáticamente. Caddy obtiene un certificado de Let's Encrypt para tu dominio, lo renueva y reenvía el tráfico a la app. La app solo escucha en `127.0.0.1:8000`.

¿Ya tienes nginx o Traefik? Responde **no** a HTTPS y apunta tu proxy al puerto 8000. En `DEPLOY.md` hay un ejemplo con nginx.

## Operación diaria

```bash
docker compose ps              # estado
docker compose logs -f web     # logs
docker compose restart web     # reiniciar la app
```

Mantén el servidor al día (una vez al mes es un buen hábito). Haz antes una copia de seguridad (ver abajo) y luego:

```bash
# 1. Sistema operativo y Docker
sudo apt update && sudo apt full-upgrade -y && sudo apt autoremove -y
[ -f /var/run/reboot-required ] && sudo reboot   # la app vuelve a arrancar sola

# 2. falcondatabase (tus datos y el .env se conservan)
git pull
./install.sh                    # también descarga las últimas imágenes de PostgreSQL 16 y Caddy

# 3. Limpia y comprueba la versión
docker image prune -f
curl -s http://127.0.0.1:8000/healthz
```

Copia de seguridad de la base de datos:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +%F).sql.gz
```

Los archivos subidos (Almacenamiento) viven en el volumen `storage`. Respáldalos también:

```bash
docker compose run --rm -v "$PWD/backups:/backups" --entrypoint tar web czf /backups/storage-$(date +%F).tar.gz -C /app/media storage
```

Restaurar una copia en una base de datos vacía:

```bash
docker compose stop web
docker compose exec -T db dropdb -U falcon falcondatabase
docker compose exec -T db createdb -U falcon falcondatabase
gunzip -c backups/falcondatabase-2026-10-25.sql.gz | docker compose exec -T db psql -q -U falcon falcondatabase
docker compose start web
```

## Instalaciones desatendidas

Para CI o herramientas de aprovisionamiento, usa `--yes` y configura todo con variables de entorno:

```bash
FALCONDB_DOMAIN=db.ejemplo.com FALCONDB_HTTPS=yes \
FALCONDB_ADMIN_USERNAME=marlon FALCONDB_ADMIN_EMAIL=yo@ejemplo.com \
./install.sh --yes
```

Ejecuta `./install.sh --help` para ver todas las opciones.
