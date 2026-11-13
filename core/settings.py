"""
Project settings.

Anything that changes between machines (passwords, hosts, URLs) is read from the
.env file using django-environ, so no secrets are written inside the code.
"""
from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
# Read the .env file if it exists (Docker also passes the same values as real environment variables)
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

# ---------------------------------------------------------------- Basics
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third party
    "rest_framework",
    "drf_spectacular",  # Swagger / OpenAPI docs
    # our apps
    "accounts",
    "rentals",
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

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# ---------------------------------------------------------------- Database (PostgreSQL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="db"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

# ---------------------------------------------------------------- Users
AUTH_USER_MODEL = "accounts.User"  # our own user model (login with email)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# A password reset link stops working after 1 hour (value is in seconds)
PASSWORD_RESET_TIMEOUT = 60 * 60

# ---------------------------------------------------------------- Django REST Framework + JWT
REST_FRAMEWORK = {
    # Every request is checked for an "Authorization: Bearer <access token>" header
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # By default every endpoint needs a logged-in user (login/register override this)
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Lets drf-spectacular build the Swagger documentation
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ---------------------------------------------------------------- Swagger docs
SPECTACULAR_SETTINGS = {
    "TITLE": "Estately Rental API",
    "DESCRIPTION": (
        "Rental management backend.\n\n"
        "**How to use the protected endpoints:** call `POST /api/auth/login/`, copy the `access` token, "
        "click the **Authorize** button, paste the token (without the word Bearer) and press Authorize."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,  # do not list the schema endpoint itself in the docs
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},  # keep the token after a page refresh
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ---------------------------------------------------------------- Redis cache (db 1)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL_CACHING"),
    }
}

# ---------------------------------------------------------------- Celery (broker = Redis db 0)
CELERY_BROKER_URL = env("REDIS_URL")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Scheduled task: every night at 00:05 close leases whose end date has passed
CELERY_BEAT_SCHEDULE = {
    "close-expired-leases": {
        "task": "rentals.tasks.close_expired_leases",
        "schedule": crontab(hour=0, minute=5),
    },
}

# ---------------------------------------------------------------- Email (SMTP)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER)

# Used to build the link inside the "reset your password" email
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")

# ---------------------------------------------------------------- Misc
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
