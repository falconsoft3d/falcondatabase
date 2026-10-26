# Cómo actualizar el servidor

Guía paso a paso para poner al día un servidor con falcondatabase instalado con `./install.sh` (Docker). Sirve para Ubuntu y Debian.

Hay tres cosas que actualizar, en este orden:

1. **El sistema operativo** (parches de seguridad, kernel).
2. **Docker** (se actualiza junto con el sistema si lo instalaste desde el repositorio oficial).
3. **falcondatabase** (el código nuevo y las imágenes de PostgreSQL y Caddy).

Tus datos (base de datos y archivos subidos) y tu configuración (`.env`) se conservan siempre.

## Actualización rápida (solo la app)

¿Solo quieres publicar los últimos cambios de falcondatabase (sin tocar el sistema)? Basta con esto:

```bash
# 1. En tu ordenador
git push

# 2. En el servidor
ssh tu-usuario@falcondatabase.com
cd ~/falcondatabase
docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +%F).sql.gz
git pull && ./install.sh
```

Comprueba con `curl -s http://127.0.0.1:8000/healthz` que la versión es la nueva (la misma que aparece arriba del todo en `/changelog/`).

**Extensión de Chrome:** si la versión trae cambios en la extensión, vuelve a descargarla desde la página **Extensión** de la web (`/extension/`), descomprímela encima de la carpeta anterior y pulsa **Recargar** (↻) en `chrome://extensions`. No hace falta volver a iniciar sesión.

Para la rutina completa (sistema operativo, Docker, copias y qué hacer si algo falla) sigue los pasos de abajo.

---

> Tiempo estimado: 5–10 minutos. La app solo deja de responder unos segundos mientras se reinician los contenedores (y uno o dos minutos si hay que reiniciar el servidor).

---

## 0. En tu ordenador: sube los cambios

El servidor descarga el código desde GitHub, así que primero sube lo que tengas en local:

```bash
git status            # que no quede nada sin guardar
git push
```

## 1. Entra en el servidor

```bash
ssh tu-usuario@falcondatabase.com
cd ~/falcondatabase          # la carpeta donde clonaste el proyecto (o /opt/falcondatabase)
```

Todos los comandos `docker compose` se ejecutan **dentro de esa carpeta**.

## 2. Copia de seguridad (no te la saltes)

```bash
mkdir -p backups

# Base de datos
docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +%F).sql.gz

# Archivos subidos (Almacenamiento)
docker compose run --rm -v "$PWD/backups:/backups" --entrypoint tar web \
  czf /backups/storage-$(date +%F).tar.gz -C /app/media storage

ls -lh backups/              # comprueba que los ficheros no están vacíos
```

Guarda también una copia fuera del servidor de vez en cuando (desde tu ordenador):

```bash
scp tu-usuario@falcondatabase.com:falcondatabase/backups/*$(date +%F)* ./
```

## 3. Actualiza el sistema operativo y Docker

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt autoremove -y
```

¿Pide reiniciar? (suele pasar cuando se actualiza el kernel):

```bash
[ -f /var/run/reboot-required ] && echo "Hay que reiniciar" || echo "No hace falta reiniciar"
```

Si hay que reiniciar:

```bash
sudo reboot
```

Espera un minuto, vuelve a entrar (`ssh …` y `cd ~/falcondatabase`) y comprueba que todo arrancó solo:

```bash
docker compose ps            # db y web (y caddy si usas HTTPS) en estado "running" / "healthy"
```

## 4. Actualiza falcondatabase

```bash
git pull
./install.sh
```

El instalador detecta que ya está instalado y **no pregunta nada ni cambia el `.env`**. Hace esto:

1. Comprueba Docker.
2. Descarga las últimas versiones de PostgreSQL 16 y Caddy.
3. Reconstruye la imagen de la app con el código nuevo.
4. Reinicia los contenedores y aplica las migraciones de la base de datos.
5. Espera a que la app responda.

Si `git pull` se queja de cambios locales, es que se editó algún archivo en el servidor. Mira cuáles con `git status`. `.env`, `docker-compose.override.yml` y `backups/` están ignorados y no molestan.

## 5. Comprueba que todo va bien

```bash
docker compose ps
curl -s http://127.0.0.1:8000/healthz       # {"status": "ok", "version": "0.7.6"}
```

Abre la web y mira la versión en el pie de página o en **Versiones** (`/changelog/`). Entra con tu usuario para confirmar que el login funciona.

## 6. Limpia

Cada actualización deja imágenes viejas de Docker ocupando disco:

```bash
docker image prune -f
df -h /                      # espacio libre en disco
```

---

## Chuleta (todo junto)

```bash
cd ~/falcondatabase
mkdir -p backups
docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +%F).sql.gz
sudo apt update && sudo apt full-upgrade -y && sudo apt autoremove -y
[ -f /var/run/reboot-required ] && sudo reboot    # si reinicia, vuelve a entrar y sigue
git pull && ./install.sh
docker image prune -f
curl -s http://127.0.0.1:8000/healthz
```

---

## Si algo sale mal

### Ver qué pasa

```bash
docker compose logs --tail 100 web          # errores de la app
docker compose logs --tail 50 db            # errores de PostgreSQL
docker compose logs --tail 50 caddy         # certificado HTTPS
```

### Volver a la versión anterior

```bash
git log --oneline -5                 # busca el commit anterior a la actualización
git checkout <commit>
./install.sh
```

Si la versión nueva ya había cambiado la base de datos (migraciones), restaura también la copia del paso 2:

```bash
docker compose stop web
docker compose exec -T db dropdb -U falcon falcondatabase
docker compose exec -T db createdb -U falcon falcondatabase
gunzip -c backups/falcondatabase-AAAA-MM-DD.sql.gz | docker compose exec -T db psql -q -U falcon falcondatabase
docker compose start web
```

Cuando esté arreglado, vuelve a la rama principal con `git checkout main`.

### Errores típicos

| Error | Solución |
|---|---|
| `Bad Request (400)` | La dirección que usas no está en `ALLOWED_HOSTS`. Ejecuta `FALCONDB_DOMAIN=falcondatabase.com ./install.sh --yes`. |
| `Forbidden (403) CSRF` al iniciar sesión | `CSRF_TRUSTED_ORIGINS` en `.env` debe coincidir exactamente con la URL del navegador (http/https y puerto). |
| `permission denied … docker.sock` | Tu usuario no está en el grupo docker: `sudo usermod -aG docker $USER`, sal y vuelve a entrar. |
| Disco lleno | `docker image prune -a -f` y borra copias viejas de `backups/`. |
| No arranca tras reiniciar | `sudo systemctl enable --now docker` y luego `docker compose up -d`. |

---

## Otros cambios con el mismo instalador

```bash
# Cambiar la dirección (por ejemplo, de la IP al dominio)
FALCONDB_DOMAIN=falcondatabase.com ./install.sh --yes

# Pasar a HTTPS con certificado gratuito (el DNS debe apuntar al servidor)
sudo ufw allow 80,443/tcp
FALCONDB_DOMAIN=falcondatabase.com FALCONDB_HTTPS=yes ./install.sh --yes

# Volver a HTTP
FALCONDB_HTTPS=no ./install.sh --yes
```

## Cada cuánto

- **Seguridad del sistema:** automática cada día si activaste `unattended-upgrades` (`sudo dpkg-reconfigure -plow unattended-upgrades`).
- **Esta rutina completa:** una vez al mes, o cuando publiques una versión nueva de falcondatabase.
- **Copias de seguridad:** antes de cada actualización. También puedes programar una copia diaria con `crontab -e`:

  ```cron
  0 3 * * * cd /home/tu-usuario/falcondatabase && docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +\%F).sql.gz
  ```

Más detalle (en inglés) en [DEPLOY.md](../DEPLOY.md#keeping-the-server-up-to-date).
