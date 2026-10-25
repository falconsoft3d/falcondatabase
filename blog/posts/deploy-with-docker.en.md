---
title: "Tutorial: deploy falcondatabase with Docker in 10 minutes"
date: 2026-10-25
category: tutorial
summary: From an empty Linux server to your own instance with HTTPS, using the step-by-step install script.
tags: docker, deployment, https, devops
---
falcondatabase ships with a Docker setup and an installer that asks a few questions and does the rest: it generates secrets, builds the image, starts PostgreSQL and the app, runs the migrations and creates your admin account.

## What you need

- A Linux server (Ubuntu 22.04/24.04, Debian 12…) with at least 1 GB of RAM.
- **Docker** with the **Compose** plugin.
- For HTTPS: a domain (for example `db.example.com`) whose DNS **A record** points to the server, and ports **80** and **443** open.

On a fresh server, update the system and open the firewall first:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git curl ufw unattended-upgrades
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
```

Then install Docker with the official script, and check it:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # then log out and back in
docker compose version
docker run --rm hello-world
```

DEPLOY.md explains each step, plus the official apt repository install, swap for small servers and a non-root user.

## 1. Get the code

```bash
git clone https://github.com/falconsoft3d/falcondatabase.git
cd falcondatabase
```

## 2. Run the installer

```bash
./install.sh
```

It goes through six steps:

1. **Checking requirements** — Docker, Compose, the Docker daemon and `curl`.
2. **Configuration** — asks for:
    - the domain or IP of the server,
    - whether to enable **automatic HTTPS** (only offered for real domains),
    - the HTTP port (8000 by default, when HTTPS is off),
    - the default language (`en` or `es`),
    - the **admin account**: username, email and password (leave it empty to generate a strong one),
    - the contact name and email for the footer.

    Everything is saved in `.env` with random values for `SECRET_KEY` and the database password.
3. **Building the image** — Python, dependencies, translations and static files.
4. **Starting the containers** — `db` (PostgreSQL 16), `web` (Gunicorn, with a `storage` volume for uploaded files) and, with HTTPS, `caddy`.
5. **Waiting for the application** — migrations run automatically and the script polls `/healthz`.
6. **Administrator account** — creates your admin user and makes it the only admin.

At the end you'll see something like:

```
falcondatabase is ready!

  Open:            https://db.example.com
  Admin user:      admin-user
  Admin password:  Xk3…  (shown only now — change it in Settings)
```

## 3. First steps after installing

1. Sign in and change the password if it was generated (**Settings → Change password**).
2. Enable **two-step authentication** for your admin account.
3. Decide whether anyone can register: **Users → Registration**.

## HTTPS explained

With HTTPS enabled the installer copies `docker-compose.https.yml` to `docker-compose.override.yml`, which Docker Compose loads automatically. Caddy obtains a Let's Encrypt certificate for your domain, renews it, and forwards traffic to the app. The app itself only listens on `127.0.0.1:8000`.

Already have nginx or Traefik? Answer **no** to HTTPS and point your proxy to port 8000. See `DEPLOY.md` for an nginx example.

## Daily operations

```bash
docker compose ps              # status
docker compose logs -f web     # logs
docker compose restart web     # restart the app
```

Keep the server up to date (once a month is a good habit). Back up first (see below), then:

```bash
# 1. Operating system and Docker
sudo apt update && sudo apt full-upgrade -y && sudo apt autoremove -y
[ -f /var/run/reboot-required ] && sudo reboot   # the app comes back on its own

# 2. falcondatabase (your data and .env are kept)
git pull
./install.sh                    # also pulls the latest PostgreSQL 16 and Caddy images

# 3. Clean up and check the version
docker image prune -f
curl -s http://127.0.0.1:8000/healthz
```

Back up the database:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +%F).sql.gz
```

Uploaded files (Storage) live in the `storage` volume. Back them up too:

```bash
docker compose run --rm -v "$PWD/backups:/backups" --entrypoint tar web czf /backups/storage-$(date +%F).tar.gz -C /app/media storage
```

Restore a backup into an empty database:

```bash
docker compose stop web
docker compose exec -T db dropdb -U falcon falcondatabase
docker compose exec -T db createdb -U falcon falcondatabase
gunzip -c backups/falcondatabase-2026-10-25.sql.gz | docker compose exec -T db psql -q -U falcon falcondatabase
docker compose start web
```

## Unattended installs

For CI or provisioning tools, pass `--yes` and configure everything with environment variables:

```bash
FALCONDB_DOMAIN=db.example.com FALCONDB_HTTPS=yes \
FALCONDB_ADMIN_USERNAME=marlon FALCONDB_ADMIN_EMAIL=me@example.com \
./install.sh --yes
```

Run `./install.sh --help` to see every option.
