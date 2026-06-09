"""
cPanel production settings.

Used by Namecheap/cPanel Python App through passenger_wsgi.py.
"""

from decouple import config

from .production import *  # noqa: F401, F403


def _csv_setting(name, default=""):
    return [item.strip() for item in config(name, default=default).split(",") if item.strip()]


MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

CSRF_TRUSTED_ORIGINS = _csv_setting(
    "CSRF_TRUSTED_ORIGINS",
    default="https://pay.syntaxasia.digital",
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Shared cPanel hosting normally does not expose Memcached by default.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
SILENCED_SYSTEM_CHECKS = ["ratelimit.E003", "ratelimit.W001"]

if DATABASES["default"].get("ENGINE") == "django.db.backends.mysql":  # noqa: F405
    DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405
    DATABASES["default"]["OPTIONS"].setdefault("charset", "utf8mb4")  # noqa: F405
    DATABASES["default"]["OPTIONS"].setdefault(  # noqa: F405
        "init_command",
        "SET sql_mode='STRICT_TRANS_TABLES'",
    )
