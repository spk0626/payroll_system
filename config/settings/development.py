"""
Development settings.
Uses SQLite for zero-setup local development.
DEBUG is True. Email is printed to console.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

DATABASE_URL = config("DATABASE_URL", default="")  # noqa: F405
if DATABASE_URL:
    import dj_database_url

    DATABASES = {  # noqa: F405
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=0),
    }
else:
    # Use SQLite in development only when no server-style database is configured.
    SQLITE_DATABASE_PATH = config("SQLITE_DATABASE_PATH", default=str(BASE_DIR / "db.sqlite3"))  # noqa: F405

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_DATABASE_PATH,
        }
    }

# Print emails to terminal by default. Set EMAIL_BACKEND in .env to test SMTP.
EMAIL_BACKEND = config(  # noqa: F405
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

# Relax security headers that break local HTTP
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# django-debug-toolbar (install separately: pip install django-debug-toolbar)
try:
    def _show_debug_toolbar(request):
        return request.path_info.startswith(f"/{ADMIN_URL}") is False  # noqa: F405

    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": _show_debug_toolbar,
    }

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
SILENCED_SYSTEM_CHECKS = ["ratelimit.E003", "ratelimit.W001"]
