"""
web_dashboard/web_dashboard/settings.py
=========================================
Django project settings.

WHY THIS EXISTS:
  - Central configuration for the Django frontend service.
  - Reads secrets from environment variables (never hardcoded).
  - Designed so switching from SQLite → PostgreSQL requires
    only a single environment variable change.

SECURITY NOTES:
  - SECRET_KEY must be overridden in production via .env
  - DEBUG must be False in production
  - ALLOWED_HOSTS must be locked down in production
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Path Setup
# ---------------------------------------------------------------------------

# web_dashboard/ directory (where manage.py lives)
BASE_DIR = Path(__file__).resolve().parent.parent

# Project root (one level above web_dashboard/)
PROJECT_ROOT = BASE_DIR.parent

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-placeholder-replace-in-production"
)

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.getenv(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost"
).split(",")

# ---------------------------------------------------------------------------
# Application Definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "crispy_forms",
    "crispy_bootstrap5",

    # Our application (Phase 8)
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "web_dashboard.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Look in each app's templates/ folder
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "web_dashboard.wsgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# SQLite for development. To switch to PostgreSQL:
#   1. pip install psycopg2-binary
#   2. Change ENGINE, NAME, USER, PASSWORD, HOST, PORT below
#   3. Run: python manage.py migrate
#
# The Django ORM abstraction means NO model code changes are needed.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / os.getenv("SQLITE_DB_PATH", "db.sqlite3"),
    }
    # PostgreSQL template (uncomment and fill when ready):
    # "default": {
    #     "ENGINE": "django.db.backends.postgresql",
    #     "NAME": os.getenv("POSTGRES_DB"),
    #     "USER": os.getenv("POSTGRES_USER"),
    #     "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
    #     "HOST": os.getenv("POSTGRES_HOST", "localhost"),
    #     "PORT": os.getenv("POSTGRES_PORT", "5432"),
    # }
}

# ---------------------------------------------------------------------------
# Password Validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static Files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / "staticfiles"   # For collectstatic in production

# ---------------------------------------------------------------------------
# Media Files (for EVTX upload storage)
# ---------------------------------------------------------------------------

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# ---------------------------------------------------------------------------
# Default Primary Key Field
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Crispy Forms
# ---------------------------------------------------------------------------

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ---------------------------------------------------------------------------
# External Services
# ---------------------------------------------------------------------------

# URL of the Flask ML inference microservice
FLASK_API_BASE_URL = os.getenv("FLASK_API_BASE_URL", "http://127.0.0.1:5000")

# ---------------------------------------------------------------------------
# Login / Logout Redirect
# ---------------------------------------------------------------------------

LOGIN_URL = "/auth/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/auth/login/"
