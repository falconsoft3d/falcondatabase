#!/usr/bin/env bash
# falcondatabase installer — sets up the app with Docker, step by step.
#
#   ./install.sh            interactive installation (or update, when .env already exists)
#   ./install.sh --yes      non-interactive: use defaults and environment variables
#   ./install.sh --help     show all options
#
# Re-running the script is safe: it keeps your .env, rebuilds the image, applies
# database migrations and restarts the containers.

set -euo pipefail

cd "$(dirname "$0")"

ASSUME_YES=false
FORCE=false
ENV_FILE=".env"
OVERRIDE_FILE="docker-compose.override.yml"
HTTPS_FILE="docker-compose.https.yml"
INSTALLER_MARK="FALCONDB_INSTALLER=1"

usage() {
  cat <<'USAGE'
Usage: ./install.sh [--yes] [--force] [--help]

  --yes     Don't ask questions. Values come from these environment variables
            (defaults in brackets):
              FALCONDB_DOMAIN          [localhost]  domain or IP address of the server
              FALCONDB_HTTPS           [no]         "yes" to enable HTTPS with Caddy
              FALCONDB_PORT            [8000]       HTTP port when HTTPS is disabled
              FALCONDB_LANGUAGE        [en]         default interface language: en or es
              FALCONDB_ADMIN_USERNAME  [admin-user]
              FALCONDB_ADMIN_EMAIL     [admin@example.com]
              FALCONDB_ADMIN_PASSWORD  [generated]
              FALCONDB_CONTACT_NAME    [the admin username]
              FALCONDB_CONTACT_EMAIL   [the admin email]
  --force   Replace an existing .env that was not created by this installer
            (a backup copy is kept).
  --help    Show this help.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=true ;;
    --force) FORCE=true ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $arg"; usage; exit 1 ;;
  esac
done

# --- output helpers -----------------------------------------------------------

if [ -t 1 ]; then
  BOLD=$'\e[1m'; DIM=$'\e[2m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; RED=$'\e[31m'; CYAN=$'\e[36m'; RESET=$'\e[0m'
else
  BOLD=""; DIM=""; GREEN=""; YELLOW=""; RED=""; CYAN=""; RESET=""
fi

STEP=0
TOTAL_STEPS=6
step() { STEP=$((STEP + 1)); printf '\n%s[%d/%d] %s%s\n' "$BOLD$CYAN" "$STEP" "$TOTAL_STEPS" "$1" "$RESET"; }
ok() { printf '  %s✓%s %s\n' "$GREEN" "$RESET" "$1"; }
info() { printf '  %s\n' "$1"; }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$RESET" "$1"; }
fail() { printf '\n%s✗ %s%s\n' "$RED" "$1" "$RESET" >&2; exit 1; }

# ask VAR "Question" "default" — keeps $VAR if already set in the environment.
ask() {
  local var="$1" question="$2" default="$3" answer
  if [ -n "${!var:-}" ]; then return; fi
  if $ASSUME_YES; then printf -v "$var" '%s' "$default"; return; fi
  read -r -p "  $question ${DIM}[$default]${RESET}: " answer
  printf -v "$var" '%s' "${answer:-$default}"
}

# ask_secret VAR "Question" — empty answer means "generate one".
ask_secret() {
  local var="$1" question="$2" answer
  if [ -n "${!var:-}" ] || $ASSUME_YES; then return; fi
  read -r -s -p "  $question ${DIM}[leave empty to generate]${RESET}: " answer
  echo
  printf -v "$var" '%s' "$answer"
}

confirm() {
  local question="$1" default="$2" answer
  if $ASSUME_YES; then [ "$default" = "y" ]; return; fi
  read -r -p "  $question ${DIM}[$( [ "$default" = "y" ] && echo "Y/n" || echo "y/N" )]${RESET}: " answer
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[YySs] ]]
}

# Double-quoted .env value (needed for spaces and non-ASCII text such as "Hernández").
quote_env() {
  local value="${1//\\/\\\\}"
  printf '"%s"' "${value//\"/\\\"}"
}

random_string() {
  LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$1" || true
}

env_get() {
  [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' || true
}

is_ip_or_local() {
  [[ "$1" == "localhost" || "$1" =~ ^[0-9.]+$ || "$1" == *:* ]]
}

printf '%s\n' "${BOLD}falcondatabase installer${RESET}"
printf '%s\n' "${DIM}Django + PostgreSQL backend for your apps — Docker setup${RESET}"

# --- 1. requirements ------------------------------------------------------------

step "Checking requirements"

command -v docker >/dev/null 2>&1 || fail "Docker is not installed. Install it from https://docs.docker.com/engine/install/ and run this script again."
ok "Docker found: $(docker --version)"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  fail "Docker Compose is not available. Install the Docker Compose plugin: https://docs.docker.com/compose/install/"
fi
ok "Docker Compose found: $("${COMPOSE[@]}" version | head -n 1)"

docker info >/dev/null 2>&1 || fail "The Docker daemon is not running (or this user can't use it). Start Docker, or run: sudo usermod -aG docker \$USER and log in again."
ok "Docker daemon is running"

command -v curl >/dev/null 2>&1 || fail "curl is required. Install it (for example: sudo apt install curl)."
ok "curl found"

# --- 2. configuration ---------------------------------------------------------

step "Configuration (.env)"

FIRST_INSTALL=true
if [ -f "$ENV_FILE" ]; then
  if grep -q "^$INSTALLER_MARK" "$ENV_FILE"; then
    FIRST_INSTALL=false
    ok "Existing configuration found in $ENV_FILE — keeping it (this is an update)"
  else
    warn "$ENV_FILE exists but was not created by this installer (it may be a development file)."
    if $FORCE || confirm "Back it up and create a new one?" "n"; then
      BACKUP="$ENV_FILE.backup-$(date +%Y%m%d-%H%M%S)"
      mv "$ENV_FILE" "$BACKUP"
      ok "Previous file saved as $BACKUP"
    else
      fail "Installation cancelled. Move $ENV_FILE away or run ./install.sh --force."
    fi
  fi
fi

GENERATED_PASSWORD=""
if $FIRST_INSTALL; then
  info "Answer a few questions. Press Enter to accept the value in brackets."
  echo
  ask FALCONDB_DOMAIN "Domain or IP address of this server" "localhost"
  FALCONDB_HTTPS_ENABLED=false
  if is_ip_or_local "$FALCONDB_DOMAIN"; then
    info "${DIM}HTTPS needs a real domain name; it stays disabled for $FALCONDB_DOMAIN.${RESET}"
  elif [ "${FALCONDB_HTTPS:-}" = "yes" ] || { ! $ASSUME_YES && [ -z "${FALCONDB_HTTPS:-}" ] \
       && confirm "Enable automatic HTTPS with Let's Encrypt? (DNS must point here, ports 80/443 open)" "y"; }; then
    FALCONDB_HTTPS_ENABLED=true
  fi
  if ! $FALCONDB_HTTPS_ENABLED; then
    ask FALCONDB_PORT "HTTP port" "8000"
  fi
  ask FALCONDB_LANGUAGE "Default interface language (en/es)" "en"
  [[ "$FALCONDB_LANGUAGE" == "es" ]] || FALCONDB_LANGUAGE="en"

  echo
  info "${BOLD}Administrator account${RESET} (the only user who manages users and sign up)"
  ask FALCONDB_ADMIN_USERNAME "Username" "admin-user"
  ask FALCONDB_ADMIN_EMAIL "Email" "admin@example.com"
  ask_secret FALCONDB_ADMIN_PASSWORD "Password"
  if [ -z "${FALCONDB_ADMIN_PASSWORD:-}" ]; then
    FALCONDB_ADMIN_PASSWORD="$(random_string 16)"
    GENERATED_PASSWORD="$FALCONDB_ADMIN_PASSWORD"
  fi
  ask FALCONDB_CONTACT_NAME "Contact name shown in the footer" "$FALCONDB_ADMIN_USERNAME"
  ask FALCONDB_CONTACT_EMAIL "Contact email shown in the footer" "$FALCONDB_ADMIN_EMAIL"

  if $FALCONDB_HTTPS_ENABLED; then
    PUBLIC_URL="https://$FALCONDB_DOMAIN"
    ALLOWED_HOSTS="$FALCONDB_DOMAIN,localhost,127.0.0.1"
    FALCONDB_PORT="8000"
    FALCONDB_BIND="127.0.0.1"
  else
    PUBLIC_URL="http://$FALCONDB_DOMAIN:$FALCONDB_PORT"
    ALLOWED_HOSTS="$FALCONDB_DOMAIN,localhost,127.0.0.1"
    FALCONDB_BIND="0.0.0.0"
  fi

  umask 077
  cat > "$ENV_FILE" <<ENV
# Generated by install.sh on $(date -u +"%Y-%m-%d %H:%M UTC"). Keep this file private.
$INSTALLER_MARK
DEBUG=false
SECRET_KEY=$(random_string 64)
ALLOWED_HOSTS=$ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS=$PUBLIC_URL
USE_HTTPS=$FALCONDB_HTTPS_ENABLED
FALCONDB_PUBLIC_URL=$PUBLIC_URL

# Network
FALCONDB_DOMAIN=$FALCONDB_DOMAIN
FALCONDB_PORT=$FALCONDB_PORT
FALCONDB_BIND=$FALCONDB_BIND

# Database (the "db" container)
POSTGRES_DB=falcondatabase
POSTGRES_USER=falcon
POSTGRES_PASSWORD=$(random_string 32)
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Application
FALCONDB_LANGUAGE=$FALCONDB_LANGUAGE
FALCONDB_CORS_ORIGINS=*
FALCONDB_CONTACT_NAME=$(quote_env "$FALCONDB_CONTACT_NAME")
FALCONDB_CONTACT_EMAIL=$(quote_env "$FALCONDB_CONTACT_EMAIL")
FALCONDB_ADMIN_USERNAME=$(quote_env "$FALCONDB_ADMIN_USERNAME")
WEB_CONCURRENCY=3
ENV
  umask 022
  ok "Configuration written to $ENV_FILE (with random secrets)"
fi

USE_HTTPS="$(env_get USE_HTTPS)"
PUBLIC_URL="$(env_get FALCONDB_PUBLIC_URL)"
PORT="$(env_get FALCONDB_PORT)"
ADMIN_USERNAME="$(env_get FALCONDB_ADMIN_USERNAME)"

if [ "$USE_HTTPS" = "true" ]; then
  cp "$HTTPS_FILE" "$OVERRIDE_FILE"
  ok "HTTPS enabled: Caddy will serve $PUBLIC_URL"
elif [ -f "$OVERRIDE_FILE" ] && grep -q "Caddy" "$OVERRIDE_FILE"; then
  rm "$OVERRIDE_FILE"
  ok "HTTPS disabled"
fi

# --- 3. build -----------------------------------------------------------------

step "Building the application image (this can take a few minutes the first time)"
"${COMPOSE[@]}" build --pull
ok "Image built"

# --- 4. start -----------------------------------------------------------------

step "Starting the containers"
"${COMPOSE[@]}" up -d --remove-orphans
ok "Containers started"

# --- 5. health check ----------------------------------------------------------

step "Waiting for the application (database migrations run on start)"
HEALTH_URL="http://127.0.0.1:${PORT:-8000}/healthz"
for attempt in $(seq 1 60); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    ok "The application answers at $HEALTH_URL"
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    warn "The application did not answer in time. Last log lines:"
    "${COMPOSE[@]}" logs --tail 40 web || true
    fail "Check the logs with: ${COMPOSE[*]} logs -f web"
  fi
  sleep 2
done

# --- 6. administrator ---------------------------------------------------------

step "Administrator account"
if [ -n "$ADMIN_USERNAME" ]; then
  "${COMPOSE[@]}" exec -T \
    -e FALCONDB_ADMIN_USERNAME="$ADMIN_USERNAME" \
    -e FALCONDB_ADMIN_EMAIL="${FALCONDB_ADMIN_EMAIL:-}" \
    -e FALCONDB_ADMIN_PASSWORD="${FALCONDB_ADMIN_PASSWORD:-}" \
    web python manage.py ensureadmin 2>&1 | sed 's/^/  /' \
    || warn "Could not set up the admin account. Fix it later with: ${COMPOSE[*]} exec web python manage.py setadmin <username>"
else
  warn "No admin username in $ENV_FILE; create one with: ${COMPOSE[*]} exec web python manage.py setadmin <username>"
fi

# --- summary ------------------------------------------------------------------

echo
printf '%s\n' "${BOLD}${GREEN}falcondatabase is ready!${RESET}"
echo
info "Open:            ${BOLD}$PUBLIC_URL${RESET}"
info "Admin user:      $ADMIN_USERNAME"
if [ -n "$GENERATED_PASSWORD" ]; then
  info "Admin password:  ${BOLD}$GENERATED_PASSWORD${RESET}  ${YELLOW}(shown only now — change it in Settings)${RESET}"
fi
echo
info "${BOLD}Useful commands${RESET}"
info "  ${COMPOSE[*]} ps                 container status"
info "  ${COMPOSE[*]} logs -f web        application logs"
info "  ./install.sh                       update after a git pull (keeps your data)"
info "  ${COMPOSE[*]} down               stop everything (data is kept in the pgdata volume)"
info "See DEPLOY.md for backups, HTTPS and troubleshooting."
