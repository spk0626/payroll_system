"""
Vercel settings.
Uses Vercel's Python runtime with an external PostgreSQL database.
"""

from decouple import config

from .production import *  # noqa: F401, F403

def _csv_setting(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in config(name, default=default).split(",") if item.strip()]


MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

ALLOWED_HOSTS = _csv_setting("ALLOWED_HOSTS")
for host in [
    ".vercel.app",
    "localhost",
    "127.0.0.1",
    config("VERCEL_URL", default=""),
    config("VERCEL_BRANCH_URL", default=""),
]:
    if host and host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = _csv_setting("CSRF_TRUSTED_ORIGINS")
for origin in [
    "https://*.vercel.app",
    f"https://{config('VERCEL_URL', default='')}",
    f"https://{config('VERCEL_BRANCH_URL', default='')}",
]:
    if origin != "https://" and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Vercel functions do not provide a long-lived local Memcached service.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.E003", "django_ratelimit.W001"]

# Runtime filesystem is ephemeral; log to stdout/stderr.
LOGGING["handlers"].pop("file", None)  # noqa: F405
LOGGING["root"]["handlers"] = ["console"]  # noqa: F405
LOGGING["loggers"]["django"]["handlers"] = ["console"]  # noqa: F405
