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

Install Docker on Ubuntu or Debian with the official script:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # then log out and back in
```

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
4. **Starting the containers** — `db` (PostgreSQL 16), `web` (Gunicorn) and, with HTTPS, `caddy`.
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

Update to a new version (your data and `.env` are kept):

```bash
git pull
./install.sh
```

Back up the database:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U falcon falcondatabase | gzip > backups/falcondatabase-$(date +%F).sql.gz
```

Restore a backup:

```bash
gunzip -c backups/falcondatabase-2026-10-25.sql.gz | docker compose exec -T db psql -U falcon falcondatabase
```

## Unattended installs

For CI or provisioning tools, pass `--yes` and configure everything with environment variables:

```bash
FALCONDB_DOMAIN=db.example.com FALCONDB_HTTPS=yes \
FALCONDB_ADMIN_USERNAME=marlon FALCONDB_ADMIN_EMAIL=me@example.com \
./install.sh --yes
```

Run `./install.sh --help` to see every option.
