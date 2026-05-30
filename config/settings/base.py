"""
Base settings for Syntax Asia Salary System.

All environments inherit from this file.
Sensitive values are read from environment variables via python-decouple.
No secrets ever appear in source code.
"""

from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", cast=Csv(), default="localhost")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "django_ratelimit",
]

LOCAL_APPS = [
    "core",
    "accounts",
    "employees",
    "payroll",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.SessionIdleTimeoutMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "core.security.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Colombo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
SALARY_UPLOADS_ROOT = BASE_DIR / "salary_uploads"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "payroll:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

ADMIN_URL = config("ADMIN_URL", default="management-portal/")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", cast=bool, default=True)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="Syntax Asia Payroll <noreply@syntaxasia.lk>")

COMPANY_NAME = config("COMPANY_NAME", default="Syntax Asia")
COMPANY_ADDRESS = config("COMPANY_ADDRESS", default="")
CURRENCY_SYMBOL = config("CURRENCY_SYMBOL", default="LKR")
SITE_URL = config("SITE_URL", default="http://localhost:8000")

SESSION_IDLE_TIMEOUT = config("SESSION_IDLE_TIMEOUT", cast=int, default=1800)
SESSION_REMEMBER_ME_AGE = 60 * 60 * 24 * 30  # 30 days
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = SESSION_IDLE_TIMEOUT

EXCEL_UPLOAD_MAX_MB = config("EXCEL_UPLOAD_MAX_MB", cast=int, default=5)
EXCEL_MAX_ROWS = config("EXCEL_MAX_ROWS", cast=int, default=500)
FILE_UPLOAD_MAX_MEMORY_SIZE = EXCEL_UPLOAD_MAX_MB * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = EXCEL_UPLOAD_MAX_MB * 1024 * 1024

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "accounts": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "employees": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "payroll": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
