# Running Guide

Quick commands for running the payroll system locally and checking deployment
settings.

## Local Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements/development.txt
copy .env.example .env
```

Update `.env` before running the app:

```env
DJANGO_SETTINGS_MODULE=config.settings.development
SECRET_KEY=replace-with-a-generated-secret
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
ADMIN_URL=management-portal/
SITE_URL=http://localhost:8004
```

Generate a local secret key:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Run Locally

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver 8004
```

Open:

```text
Employee portal: http://127.0.0.1:8004/
Admin portal:    http://127.0.0.1:8004/management-portal/
```

## Checks

Run these before pushing:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest -q
```

For focused checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\accounts\test_auth.py -q
.\.venv\Scripts\python.exe -m pytest tests\payroll -q
```

## Vercel Notes

Use `feature/vercel-deployment` for Vercel deployment fixes unless a newer
deployment branch is created.

Required Vercel project settings:

```text
Framework Preset: Other
Install Command: python -m pip install --break-system-packages -r requirements.txt
Build Command: python manage.py collectstatic --noinput --settings=config.settings.vercel
Output Directory: leave blank
Run Command: leave blank
```

Required Vercel environment variables:

```env
DJANGO_SETTINGS_MODULE=config.settings.vercel
SECRET_KEY=<generated-secret>
ALLOWED_HOSTS=.vercel.app,<custom-domain-if-any>
CSRF_TRUSTED_ORIGINS=https://*.vercel.app,https://<custom-domain-if-any>
DATABASE_URL=<postgres-url>
ADMIN_URL=management-portal/
SITE_URL=https://<vercel-domain>
```

Do not use SQLite on Vercel for real payroll data. Use PostgreSQL.
