"""
Django settings for the PropSuite project.

Configuration is driven by environment variables (see `.env`) so the same
codebase runs on SQLite in development and PostgreSQL in production without
code changes. Powered by django-environ.
"""

import sys
from pathlib import Path

import environ

# ── Paths ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── Environment ────────────────────────────────────────
# Read variables from the .env file at the project root.
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Absolute base URL used when building links outside a request (e.g. the
# content encoded into each property's QR code).
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")

# True while running the test suite — lets code skip side effects such as
# writing QR image files to disk for every created property.
TESTING = "test" in sys.argv


# ── Applications ───────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "crispy_forms",
    "crispy_bootstrap5",
]

LOCAL_APPS = [
    "accounts",
    "properties",
    "tenants",
    "leases",
    "payments",
    "maintenance",
    "inspections",
    "notifications",
    "expenses",
    "dashboard",
    "api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static files in production; must sit right after
    # SecurityMiddleware and before everything else.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        # Project-wide templates directory (base.html, shared partials).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Exposes unread notification count to every template.
                "notifications.context_processors.unread_notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ── Database ───────────────────────────────────────────
# DATABASE_URL drives the engine: sqlite:// for dev, postgres:// for prod.
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}


# ── Authentication ─────────────────────────────────────
# Custom user model — set BEFORE the first migration and never changed.
AUTH_USER_MODEL = "accounts.User"

# Allow login by email or username (see accounts/backends.py).
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailOrUsernameBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Login / logout redirect flow. Post-login routing by role is handled by a
# dedicated redirect view (see accounts app), which LOGIN_REDIRECT_URL targets.
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:redirect"
LOGOUT_REDIRECT_URL = "accounts:login"


# ── Internationalization ───────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


# ── Static & media files ───────────────────────────────
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Static/media storage. The hashed WhiteNoise manifest storage needs a
# manifest built by collectstatic, which isn't present during development —
# so it's only switched on in production (see the `if not DEBUG` block below).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Crispy Forms (Bootstrap 5) ─────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# ── Django REST Framework + JWT ────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}


# ── Email ──────────────────────────────────────────────
# Console backend in development prints emails to the terminal.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="PropSuite <no-reply@propsuite.local>")


# ── Messages framework ─────────────────────────────────
# Map Django message tags to Bootstrap 5 alert classes.
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}


# ── Production security ─────────────────────────────────
# These harden the deployment and only switch on when DEBUG is False, so local
# development over http keeps working. Individual toggles are env-overridable.
# Hosts allowed to submit forms over HTTPS (comma-separated in .env):
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS", default=[])

if not DEBUG:
    # Compressed, hashed static files with far-future caching (needs
    # `collectstatic`). Only in production so dev doesn't need a manifest.
    STORAGES["staticfiles"]["BACKEND"] = (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )

    # Redirect all http traffic to https (disable if TLS is terminated
    # upstream and you don't want a redirect loop).
    SECURE_SSL_REDIRECT = env("SECURE_SSL_REDIRECT", default=True)
    # Trust the X-Forwarded-Proto header from the proxy/load balancer.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # HSTS — start small, raise to a year (31536000) once you're confident.
    SECURE_HSTS_SECONDS = env("SECURE_HSTS_SECONDS", default=3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Only send cookies over https.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Misc hardening.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_HTTPONLY = True
