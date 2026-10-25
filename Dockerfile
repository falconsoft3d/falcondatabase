# falcondatabase — production image (Gunicorn + WhiteNoise).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gettext compiles the translations (compilemessages).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Build-time only settings: no database is needed for these two commands.
RUN SECRET_KEY=build-only DEBUG=false python manage.py compilemessages --ignore=.venv \
    && SECRET_KEY=build-only DEBUG=false python manage.py collectstatic --noinput \
    && chmod +x docker/entrypoint.sh \
    && useradd --create-home --uid 10001 falcon \
    && chown -R falcon:falcon /app

USER falcon
EXPOSE 8000

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers ${WEB_CONCURRENCY:-3} --timeout 60 --access-logfile - --error-logfile -"]
