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

## cPanel Notes

Use `feature/cpanel-deployment` for Namecheap/cPanel deployment fixes.

Required cPanel Python App settings:

```text
Application root: /pay.syntaxasia.digital
Application URL: pay.syntaxasia.digital
Startup file: passenger_wsgi.py
```

Required cPanel environment variables:

```env
DJANGO_SETTINGS_MODULE=config.settings.cpanel
SECRET_KEY=<generated-secret>
ALLOWED_HOSTS=pay.syntaxasia.digital
CSRF_TRUSTED_ORIGINS=https://pay.syntaxasia.digital
DATABASE_URL=mysql://<user>:<password>@localhost:3306/<database>
ADMIN_URL=management-portal/
SITE_URL=https://pay.syntaxasia.digital
```

Run deployment commands from cPanel Terminal or SSH:

```bash
pip install -r requirements/production.txt
python manage.py migrate --settings=config.settings.cpanel
python manage.py loaddata payroll_postgres_import.json --settings=config.settings.cpanel
python manage.py seed_default_users --settings=config.settings.cpanel
python manage.py collectstatic --noinput --settings=config.settings.cpanel
```

Initial deployment credentials are documented in `docs/cpanel-deployment.md`.
Rotate them immediately after handover.
