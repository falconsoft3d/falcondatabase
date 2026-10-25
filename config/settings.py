"""Django settings for falcondatabase."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEFAULT_SECRET_KEY = "dev-insecure-change-me"
SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY)
DEBUG = env_bool("DEBUG", True)
if not DEBUG and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured("Set SECRET_KEY when DEBUG is false.")
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
# Forms opened at https://<one of our hosts> are always accepted, even when a proxy
# in front terminates HTTPS without telling Django (USE_HTTPS=false).
CSRF_TRUSTED_ORIGINS += [
    f"https://{host}" for host in ALLOWED_HOSTS
    if host not in ("*", "localhost", "127.0.0.1") and not host.startswith(".")
    and f"https://{host}" not in CSRF_TRUSTED_ORIGINS
]
CSRF_FAILURE_VIEW = "core.views.csrf_failure"

# Behind an HTTPS reverse proxy (Caddy, nginx...) that sets X-Forwarded-Proto.
USE_HTTPS = env_bool("USE_HTTPS", False)
if USE_HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 0))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "projects",
    "api",
    "blog",
    "analytics",
    "portal",
    "storage",
]

MIDDLEWARE = [
    "api.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "falcondatabase"),
        "USER": os.environ.get("POSTGRES_USER", ""),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = ["core.backends.UsernameOrEmailBackend"]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "home"

# Default interface language ("es" or "en"); each visitor can switch it.
LANGUAGE_CODE = os.environ.get("FALCONDB_LANGUAGE", "es")
LANGUAGES = [("es", "Español"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Files uploaded to the projects' storage buckets (a Docker volume in production).
FALCONDB_STORAGE_ROOT = os.environ.get("FALCONDB_STORAGE_ROOT", str(BASE_DIR / "media" / "storage"))
FALCONDB_STORAGE_MAX_FILE_MB = int(os.environ.get("FALCONDB_STORAGE_MAX_FILE_MB", 50))
FALCONDB_STORAGE_QUOTA_MB = int(os.environ.get("FALCONDB_STORAGE_QUOTA_MB", 1024))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- falcondatabase ---------------------------------------------------------
# Origins allowed to call the REST API from a browser. "*" allows any origin.
FALCONDB_CORS_ORIGINS = env_list("FALCONDB_CORS_ORIGINS", "*")
# Lifetime of the tokens issued to the end users of each project (seconds).
FALCONDB_TOKEN_MAX_AGE = int(os.environ.get("FALCONDB_TOKEN_MAX_AGE", 60 * 60 * 24 * 7))
# Trust X-Forwarded-For (set by the reverse proxy) to get the visitor IP for analytics.
FALCONDB_TRUST_PROXY = env_bool("FALCONDB_TRUST_PROXY", USE_HTTPS)
# Maximum number of rows returned by a single API request.
FALCONDB_MAX_PAGE_SIZE = int(os.environ.get("FALCONDB_MAX_PAGE_SIZE", 1000))
# Contact shown in the site footer.
FALCONDB_CONTACT_NAME = os.environ.get("FALCONDB_CONTACT_NAME", "Marlon Falcon Hernández")
FALCONDB_CONTACT_EMAIL = os.environ.get("FALCONDB_CONTACT_EMAIL", "mfalconsoft@gmail.com")
