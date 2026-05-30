"""
Development settings.
Uses SQLite for zero-setup local development.
DEBUG is True. Email is printed to console.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

# Use SQLite in development — no PostgreSQL setup required to start working
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# Print emails to terminal in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Relax security headers that break local HTTP
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# django-debug-toolbar (install separately: pip install django-debug-toolbar)
try:
    import debug_toolbar  # noqa: F401
    INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
    INTERNAL_IPS = ["127.0.0.1"]
except ImportError:
    pass

# django-ratelimit needs a cache backend. Use local memory cache in development.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
# Silence the ratelimit shared-cache warning in development only.
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003", "django_ratelimit.W001"]