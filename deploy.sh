#!/usr/bin/env bash
# Update this server to the latest commit of the branch: back up the database,
# pull and run ./install.sh --yes (which rebuilds, restarts and waits for /healthz).
#
# Run by .github/workflows/deploy.yml on every push to main, or by hand:
#   cd /opt/falcondatabase && ./deploy.sh
#
# Environment: DEPLOY_BRANCH [main], DEPLOY_KEEP_BACKUPS [14].

set -euo pipefail
cd "$(dirname "$0")"

BRANCH="${DEPLOY_BRANCH:-main}"
KEEP="${DEPLOY_KEEP_BACKUPS:-14}"

if docker compose version >/dev/null 2>&1; then COMPOSE=(docker compose); else COMPOSE=(docker-compose); fi

echo "==> Backup"
mkdir -p backups
if "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx db; then
  file="backups/falcondatabase-$(date +%F-%H%M%S).sql.gz"
  "${COMPOSE[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$file"
  echo "    $file"
  # Keep only the newest $KEEP automatic backups.
  ls -1t backups/falcondatabase-*-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
else
  echo "    database not running, skipped"
fi

echo "==> Code ($BRANCH)"
before="$(git rev-parse --short HEAD)"
git fetch --quiet origin "$BRANCH"
git checkout --quiet "$BRANCH"
git merge --ff-only --quiet "origin/$BRANCH"
echo "    $before → $(git rev-parse --short HEAD)"

echo "==> Install"
./install.sh --yes

port="$(grep -E '^FALCONDB_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '"' || true)"
echo "==> Done: $(curl -fsS "http://127.0.0.1:${port:-8000}/healthz" || echo 'healthz not reachable')"
