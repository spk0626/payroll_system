"""
Base settings for Syntax Asia Salary System.

All environments inherit from this file.
Sensitive values are read from environment variables via python-decouple.
No secrets ever appear in source code.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ─── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv(), default="localhost")

# ─── Application definition ───────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS: list[str] = [
    # django-otp (MFA) — added in D2
    # django-ratelimit  — added in D2
]

LOCAL_APPS = [
    "core",
    "accounts",
    "employees",
    "payroll",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.AdminPortalStaffOnlyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Session idle timeout — added in D2
    # "accounts.middleware.SessionIdleTimeoutMiddleware",
]

ROOT_URLCONF = "config.urls"

# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.company_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ─── Database ─────────────────────────────────────────────────────────────────
# Parsed from DATABASE_URL in each environment's settings.
# Default kept here only for initial migrate; overridden in dev/prod.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ─── Password validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Colombo"
USE_I18N = True
USE_TZ = True

# ─── Static files ─────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ─── Media / uploads ──────────────────────────────────────────────────────────
# Public media (e.g. company logo)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Excel uploads stored OUTSIDE the web-served media root.
# Nginx must NOT serve this directory. Django serves downloads through a view.
SALARY_UPLOADS_ROOT = BASE_DIR / "salary_uploads"

# ─── Auth ─────────────────────────────────────────────────────────────────────
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "payroll:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# ─── Admin ────────────────────────────────────────────────────────────────────
# The admin is served at a custom path, not the default /admin/.
# This value is read in config/urls.py.
ADMIN_URL = config("ADMIN_URL", default="management-portal/")

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # overridden per environment
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=bool, default=True)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Syntax Asia Payroll <noreply@syntaxasia.lk>")

# ─── Application-specific settings ────────────────────────────────────────────
COMPANY_NAME = config("COMPANY_NAME", default="Syntax Asia")
COMPANY_ADDRESS = config("COMPANY_ADDRESS", default="")
CURRENCY_SYMBOL = config("CURRENCY_SYMBOL", default="LKR")

# Seconds of browser inactivity before session is terminated
SESSION_IDLE_TIMEOUT = config("SESSION_IDLE_TIMEOUT", cast=int, default=1800)

# Excel upload constraints
EXCEL_UPLOAD_MAX_MB = config("EXCEL_UPLOAD_MAX_MB", cast=int, default=5)
EXCEL_MAX_ROWS = config("EXCEL_MAX_ROWS", cast=int, default=500)

FILE_UPLOAD_MAX_MEMORY_SIZE = EXCEL_UPLOAD_MAX_MB * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = EXCEL_UPLOAD_MAX_MB * 1024 * 1024

# ─── Security headers (all enforced in production; mild in dev) ───────────────
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ─── Default primary key ──────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "employees": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "payroll": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
