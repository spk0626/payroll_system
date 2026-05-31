"""
Vercel settings.
Uses Vercel's Python runtime with an external PostgreSQL database.
"""

from decouple import Csv, config

from .production import *  # noqa: F401, F403

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    cast=Csv(),
    default=".vercel.app,localhost,127.0.0.1",
)

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    cast=Csv(),
    default="https://*.vercel.app",
)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Vercel functions do not provide a long-lived local Memcached service.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003", "django_ratelimit.W001"]

# Runtime filesystem is ephemeral; log to stdout/stderr.
LOGGING["root"]["handlers"] = ["console"]  # noqa: F405
LOGGING["loggers"]["django"]["handlers"] = ["console"]  # noqa: F405
