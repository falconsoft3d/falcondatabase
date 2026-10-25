# Deploying falcondatabase

This guide installs falcondatabase on a server with Docker, step by step, and covers HTTPS, updates, backups and troubleshooting.

- [How it runs](#how-it-runs)
- [Requirements](#requirements)
- [Install with the script (recommended)](#install-with-the-script-recommended)
- [Unattended install](#unattended-install)
- [HTTPS](#https)
- [Manual install (without the script)](#manual-install-without-the-script)
- [Day-to-day operations](#day-to-day-operations)
- [Backups and restore](#backups-and-restore)
- [Configuration reference](#configuration-reference)
- [Security checklist](#security-checklist)
- [Troubleshooting](#troubleshooting)
- [Uninstall](#uninstall)

## How it runs

```
            ┌──────────── docker compose ────────────┐
 Internet ──▶ caddy :80/:443 ──▶ web :8000 ──▶ db :5432 │
            │ (optional, HTTPS)   Gunicorn     PostgreSQL 16
            │                     + Django     volume: pgdata
            └────────────────────────────────────────┘
```

| Service | Image | Role |
|---|---|---|
| `db` | `postgres:16-alpine` | Database. Data lives in the `pgdata` volume. Not exposed outside Docker. |
| `web` | built from `Dockerfile` | The app: Gunicorn + Django. Static files are served by WhiteNoise. Runs database migrations on every start. Uploaded files live in the `storage` volume. |
| `caddy` | `caddy:2` | Only with HTTPS. Gets and renews a Let's Encrypt certificate and proxies to `web`. |

Files involved:

| File | Purpose |
|---|---|
| `install.sh` | Interactive installer and updater |
| `Dockerfile` | Production image (Python 3.13, translations compiled, static files collected) |
| `docker-compose.yml` | `db` + `web` |
| `docker-compose.https.yml` | `caddy`. The installer copies it to `docker-compose.override.yml` when HTTPS is enabled. |
| `docker/Caddyfile` | Caddy configuration |
| `docker/entrypoint.sh` | Runs `migrate`, then Gunicorn |
| `.env` | Your configuration and secrets (created by the installer, never committed) |

## Requirements

- A Linux server (Ubuntu 22.04/24.04, Debian 12 or similar) with **1 GB RAM** or more and ~5 GB of disk. macOS with Docker Desktop also works for testing.
- **Docker Engine 20.10+** with the **Compose** plugin (`docker compose`). The legacy `docker-compose` binary also works.
- `git` and `curl`.
- For HTTPS: a **domain name** with a DNS **A** (and/or **AAAA**) record pointing to the server, and ports **80** and **443** open in the firewall.

Install Docker on Ubuntu/Debian:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER      # log out and back in afterwards
docker compose version             # check the Compose plugin
```

Open the firewall if you use `ufw`:

```bash
sudo ufw allow 80,443/tcp      # HTTPS install
sudo ufw allow 8000/tcp        # HTTP-only install on port 8000
```

## Install with the script (recommended)

### Step 1 — Get the code

```bash
sudo mkdir -p /opt/falcondatabase && sudo chown $USER /opt/falcondatabase
git clone https://github.com/falconsoft3d/falcondatabase.git /opt/falcondatabase
cd /opt/falcondatabase
```

### Step 2 — Run the installer

```bash
./install.sh
```

The script runs six steps and tells you what it is doing at each one.

**[1/6] Checking requirements.** Docker, Docker Compose, a running Docker daemon and `curl`. If something is missing it stops with instructions.

**[2/6] Configuration.** It asks the following questions. Press Enter to accept the default in brackets.

| Question | Default | Notes |
|---|---|---|
| Domain or IP address of this server | `localhost` | e.g. `db.example.com` or `203.0.113.10` |
| Enable automatic HTTPS? | yes | Only asked for real domains. Needs DNS + ports 80/443. |
| HTTP port | `8000` | Only when HTTPS is disabled |
| Default interface language | `en` | `en` or `es`. Visitors can switch it. |
| Admin username / email / password | `admin-user` / `admin@example.com` / generated | Leave the password empty to generate a strong one |
| Contact name / email | the admin's | Shown in the footer and the cookie policy |

It then writes `.env` (permissions `600`) with a random `SECRET_KEY` and database password. When HTTPS is enabled it also creates `docker-compose.override.yml`.

**[3/6] Building the application image.** Takes a few minutes the first time.

**[4/6] Starting the containers.** `docker compose up -d`.

**[5/6] Waiting for the application.** Migrations run automatically. The script polls `http://127.0.0.1:<port>/healthz` for up to two minutes and prints the logs if the app doesn't answer.

**[6/6] Administrator account.** Creates the admin user (if it doesn't exist) and makes it the **only** admin.

At the end you get the URL and, if it was generated, the admin password. It is **shown only once**, so save it.

```
falcondatabase is ready!

  Open:            https://db.example.com
  Admin user:      admin-user
  Admin password:  Xk3…  (shown only now — change it in Settings)
```

### Step 3 — After installing

1. Open the URL and sign in with the admin account.
2. **Settings → Change password** if the password was generated.
3. **Settings → Two-step authentication**: enable it for the admin.
4. **Users → Registration**: decide whether anyone can sign up, or only you create accounts.

## Unattended install

Use `--yes` to skip all questions. Values come from environment variables, and anything missing uses its default:

```bash
FALCONDB_DOMAIN=db.example.com \
FALCONDB_HTTPS=yes \
FALCONDB_LANGUAGE=en \
FALCONDB_ADMIN_USERNAME=marlon \
FALCONDB_ADMIN_EMAIL=mfalconsoft@gmail.com \
FALCONDB_ADMIN_PASSWORD='a-strong-password' \
FALCONDB_CONTACT_NAME="Marlon Falcon Hernández" \
FALCONDB_CONTACT_EMAIL=mfalconsoft@gmail.com \
./install.sh --yes
```

| Variable | Default |
|---|---|
| `FALCONDB_DOMAIN` | `localhost` |
| `FALCONDB_HTTPS` | `no` (with `--yes`, HTTPS is only enabled when this is `yes`) |
| `FALCONDB_PORT` | `8000` |
| `FALCONDB_LANGUAGE` | `en` |
| `FALCONDB_ADMIN_USERNAME` / `_EMAIL` / `_PASSWORD` | `admin-user` / `admin@example.com` / generated |
| `FALCONDB_CONTACT_NAME` / `_EMAIL` | the admin's |

Other options: `--force` replaces an existing `.env` that wasn't created by the installer (a backup copy is kept). `--help` lists everything.

## HTTPS

### Option A — Built-in Caddy (automatic)

Answer **yes** to HTTPS during the install. Then:

- Caddy listens on ports 80 and 443, gets a Let's Encrypt certificate for `FALCONDB_DOMAIN` and renews it automatically.
- The app only listens on `127.0.0.1:8000`, so it can't be reached around the proxy.
- `.env` gets `USE_HTTPS=true` (secure cookies, `X-Forwarded-Proto`) and `CSRF_TRUSTED_ORIGINS=https://<domain>`.

Certificates are stored in the `caddy_data` volume.

### Option B — Your own reverse proxy (nginx, Traefik…)

Answer **no** to HTTPS, then edit `.env`:

```bash
USE_HTTPS=true
ALLOWED_HOSTS=db.example.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://db.example.com
FALCONDB_PUBLIC_URL=https://db.example.com
FALCONDB_BIND=127.0.0.1
FALCONDB_PORT=8000
```

Apply it with `docker compose up -d`. Example nginx site (certificates from certbot):

```nginx
server {
    listen 80;
    server_name db.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name db.example.com;

    ssl_certificate     /etc/letsencrypt/live/db.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/db.example.com/privkey.pem;

    client_max_body_size 60m;   # keep it above FALCONDB_STORAGE_MAX_FILE_MB

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Switching an existing HTTP install to HTTPS

1. Point the domain's DNS to the server and open ports 80/443.
2. Edit `.env`: set `FALCONDB_DOMAIN`, `USE_HTTPS=true`, `FALCONDB_BIND=127.0.0.1`, `FALCONDB_PORT=8000`, add the domain to `ALLOWED_HOSTS`, and set `CSRF_TRUSTED_ORIGINS` and `FALCONDB_PUBLIC_URL` to `https://<domain>`.
3. Run `./install.sh` again. With `USE_HTTPS=true` it enables Caddy.

## Manual install (without the script)

If you prefer to do every step yourself:

```bash
# 1. Code
git clone https://github.com/falconsoft3d/falcondatabase.git && cd falcondatabase

# 2. Configuration
cp .env.example .env
nano .env
```

Set at least:

```bash
DEBUG=false
SECRET_KEY=<a long random string>          # e.g. openssl rand -base64 48
ALLOWED_HOSTS=db.example.com,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://db.example.com:8000
POSTGRES_PASSWORD=<another random string>
FALCONDB_LANGUAGE=en
```

`POSTGRES_HOST` and `POSTGRES_PORT` are set by `docker-compose.yml`, so you don't need to change them.

```bash
# 3. Build and start
docker compose up -d --build

# 4. Check
docker compose ps
curl http://127.0.0.1:8000/healthz          # {"status": "ok"}

# 5. Admin account
docker compose exec \
  -e FALCONDB_ADMIN_USERNAME=marlon \
  -e FALCONDB_ADMIN_EMAIL=mfalconsoft@gmail.com \
  -e FALCONDB_ADMIN_PASSWORD='a-strong-password' \
  web python manage.py ensureadmin
```

For HTTPS with Caddy: `cp docker-compose.https.yml docker-compose.override.yml`, set `FALCONDB_DOMAIN` and the HTTPS variables from Option B, then `docker compose up -d`.

> A `.env` written by hand doesn't carry the installer marker (`FALCONDB_INSTALLER=1`). If you later run `./install.sh`, add that line to keep your file, or let the installer back it up and create a new one.

## Day-to-day operations

```bash
docker compose ps                      # status and health
docker compose logs -f web             # application logs (Ctrl+C to exit)
docker compose logs -f caddy           # HTTPS proxy logs
docker compose restart web             # restart the app
docker compose down                    # stop everything (data is kept)
docker compose up -d                   # start again
```

### Updating to a new version

```bash
cd /opt/falcondatabase
git pull
./install.sh
```

The installer keeps `.env` and your data, rebuilds the image, applies the new migrations and restarts the containers. Take a backup first (next section).

### Administration commands

```bash
# Make a user the only admin
docker compose exec web python manage.py setadmin <username>

# Change any user's password from the terminal
docker compose exec web python manage.py changepassword <username>

# Django shell
docker compose exec web python manage.py shell

# PostgreSQL console
docker compose exec db psql -U falcon falcondatabase
```

From the web interface, the admin can also reset passwords and two-step authentication at **Users** (`/users/`).

## Backups and restore

### Back up

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +%F).sql.gz
```

The dump contains the database: accounts, projects, every project schema with its tables and data, app users, analytics and profile pictures. **Uploaded files** (Storage) live in the `storage` volume. Back them up too:

```bash
docker compose run --rm -v "$PWD/backups:/backups" --entrypoint tar web czf /backups/storage-$(date +%F).tar.gz -C /app/media storage
```

Daily backup at 03:00 with cron (`crontab -e`), keeping 14 days:

```cron
0 3 * * * cd /opt/falcondatabase && docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +\%F).sql.gz && find backups -name '*.sql.gz' -mtime +14 -delete
```

Copy the `backups/` folder off the server regularly, for example with `rsync` or object storage.

Also keep a copy of `.env`. Without its `SECRET_KEY`, sessions and the tokens of your apps' users stop working.

### Restore

Restore the files (if you backed them up):

```bash
docker compose run --rm -v "$PWD/backups:/backups" --entrypoint tar web xzf /backups/storage-2026-10-25.tar.gz -C /app/media
```

Restore into an **empty** database:

```bash
docker compose stop web
docker compose exec -T db dropdb -U falcon falcondatabase
docker compose exec -T db createdb -U falcon falcondatabase
gunzip -c backups/falcondatabase-2026-10-25.sql.gz | docker compose exec -T db psql -q -U falcon falcondatabase
docker compose start web
```

## Configuration reference

All settings live in `.env`. After editing it, apply the changes with `docker compose up -d`.

| Variable | Set by installer | Description |
|---|---|---|
| `FALCONDB_INSTALLER` | `1` | Marks the file as created by `install.sh` |
| `DEBUG` | `false` | Never `true` in production |
| `SECRET_KEY` | random | Signs sessions and app tokens. Keep it secret and backed up. |
| `ALLOWED_HOSTS` | domain + localhost | Host names the app answers to |
| `CSRF_TRUSTED_ORIGINS` | public URL | Origin used by the browser for forms |
| `USE_HTTPS` | `true`/`false` | Secure cookies and trust `X-Forwarded-Proto` from the proxy |
| `SECURE_HSTS_SECONDS` | – | Optional HSTS duration when `USE_HTTPS=true` (e.g. `31536000`) |
| `FALCONDB_PUBLIC_URL` | public URL | Shown by the installer |
| `FALCONDB_DOMAIN` | domain | Used by Caddy |
| `FALCONDB_PORT` | `8000` | Host port of the app |
| `FALCONDB_BIND` | `0.0.0.0` or `127.0.0.1` | Host interface of the app (`127.0.0.1` behind a proxy) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `falcondatabase` / `falcon` / random | Database credentials. Only used when the volume is first created. |
| `FALCONDB_LANGUAGE` | `en`/`es` | Default interface language |
| `FALCONDB_CORS_ORIGINS` | `*` | Origins allowed to call the API from a browser, comma separated |
| `FALCONDB_TOKEN_MAX_AGE` | – (7 days) | Lifetime of app user tokens, in seconds |
| `FALCONDB_MAX_PAGE_SIZE` | – (1000) | Maximum rows per API request |
| `FALCONDB_TRUST_PROXY` | – (= `USE_HTTPS`) | Read the visitor IP for analytics from `X-Forwarded-For`. Keep it `true` behind Caddy/nginx. |
| `FALCONDB_CONTACT_NAME` / `FALCONDB_CONTACT_EMAIL` | your answers | Footer and cookie policy contact |
| `FALCONDB_ADMIN_USERNAME` | your answer | Used by the installer to keep the admin on updates |
| `WEB_CONCURRENCY` | `3` | Gunicorn workers (about 2 × CPU cores + 1) |
| `FALCONDB_STORAGE_MAX_FILE_MB` | – (50) | Maximum size of one uploaded file |
| `FALCONDB_STORAGE_QUOTA_MB` | – (1024) | Maximum storage per project |
| `LOG_LEVEL` | – (`INFO`) | Application log level |

## Security checklist

- [ ] `DEBUG=false` and a long random `SECRET_KEY` (the installer does both).
- [ ] HTTPS enabled (Caddy or your own proxy) and `USE_HTTPS=true`.
- [ ] Only ports 22, 80 and 443 open. The database is never exposed.
- [ ] Admin account with a strong password and **two-step authentication**.
- [ ] Public sign up disabled if only you should create accounts (**Users → Registration**).
- [ ] `FALCONDB_CORS_ORIGINS` limited to your frontends' domains if you know them.
- [ ] Daily backups copied off the server, plus a copy of `.env`.
- [ ] `git pull && ./install.sh` regularly to get updates.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `The Docker daemon is not running` | Start Docker (`sudo systemctl start docker`). For `permission denied` on the socket: `sudo usermod -aG docker $USER`, then log in again. |
| `port is already allocated` | Another service uses the port. Change `FALCONDB_PORT` in `.env` (or stop the other service) and run `docker compose up -d`. |
| The installer says the app did not answer in time | Read `docker compose logs web`. Common causes: a wrong value in `.env`, or the server ran out of memory during the first start. |
| `Bad Request (400)` in the browser | The host name isn't in `ALLOWED_HOSTS`. Add it and run `docker compose up -d`. |
| `Forbidden (403) CSRF verification failed` when signing in | `CSRF_TRUSTED_ORIGINS` must match the exact URL in the browser (scheme, host and port). Behind HTTPS also set `USE_HTTPS=true`. |
| Caddy can't get a certificate | Check that DNS points to the server (`dig +short db.example.com`) and that ports 80/443 are reachable from the internet. See `docker compose logs caddy`. |
| `unexpected character … in variable name` when running Compose | Old Compose versions need values with spaces or accents in quotes: `FALCONDB_CONTACT_NAME="Marlon Falcon Hernández"`. The installer already writes them that way. |
| `Set SECRET_KEY when DEBUG is false` | `.env` is missing `SECRET_KEY`. Generate one: `openssl rand -base64 48`. |
| Changed `POSTGRES_PASSWORD` and now the app can't connect | The password is only applied when the volume is created. Change it inside PostgreSQL too: `docker compose exec db psql -U falcon -c "ALTER USER falcon PASSWORD 'new'"`. |
| All analytics visitors appear to come from the same place | The app is behind a proxy but doesn't trust `X-Forwarded-For`. Set `FALCONDB_TRUST_PROXY=true` (automatic with `USE_HTTPS=true`). |
| Locked out of the admin account (lost phone and recovery codes) | `docker compose exec web python manage.py shell -c "from core.models import TwoFactor; TwoFactor.objects.filter(user__username='marlon').delete()"` |

Health check endpoint: `GET /healthz` returns `{"status": "ok", "version": "<x.y.z>"}` when the app and the database work, and `503` otherwise.

## Uninstall

```bash
cd /opt/falcondatabase
docker compose down            # stop and remove the containers, keep the data
docker compose down -v         # ⚠️ also delete the volumes: database and certificates
docker image rm falcondatabase:latest
```

Back up first: `down -v` deletes every project and every row permanently.
