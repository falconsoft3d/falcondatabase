#!/bin/sh
# Apply database migrations, then start the command (Gunicorn by default).
set -e

python manage.py migrate --noinput

exec "$@"
