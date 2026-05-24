"""
Production settings.
PostgreSQL, SMTP email, strict security headers, no debug.
"""

from decouple import config
from .base import *  # noqa: F401, F403

DEBUG = False

# ─── Database ─────────────────────────────────────────────────────────────────
import dj_database_url  # type: ignore  # noqa: E402

DATABASES = {  # noqa: F405
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ─── Security ─────────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000          # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SECURE = True

# ─── Error reporting ──────────────────────────────────────────────────────────
_admins_email = config("ADMINS_EMAIL", default="")
if _admins_email:
    ADMINS = [("Syntax Asia Admin", _admins_email)]

# ─── Logging to file in production ────────────────────────────────────────────
LOGGING["handlers"]["file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": BASE_DIR / "logs" / "app.log",  # noqa: F405
    "maxBytes": 10 * 1024 * 1024,  # 10 MB
    "backupCount": 5,
    "formatter": "verbose",
}
LOGGING["root"]["handlers"] = ["file"]  # noqa: F405
