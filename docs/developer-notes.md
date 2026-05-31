# Developer Notes

Internal engineering notes for setup, deployment options, and implemented
features that are intentionally not described in the client-facing README.

## Local Setup

```bash
git clone <repo-url>
cd payroll_system

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements/development.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

On macOS/Linux:

```bash
source .venv/bin/activate
cp .env.example .env
```

Generate a local secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Environment File

`.env` is intentionally not committed. Create it manually on each PC or server.

Minimum local values:

```env
DJANGO_SETTINGS_MODULE=config.settings.development
SECRET_KEY=replace-with-generated-secret
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
ADMIN_URL=management-portal/
COMPANY_NAME=Syntax Asia
CURRENCY_SYMBOL=LKR
SITE_URL=http://localhost:8000
```

For Gmail SMTP testing:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-test-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Syntax Asia Payroll <your-test-gmail@gmail.com>
```

## Files To Create Manually On A New PC

These are intentionally not committed:

```text
.env
db.sqlite3
salary_uploads/
media/
.venv/
```

Recreate `.venv` with `pip install -r requirements/development.txt`.

## Database Notes

SQLite is acceptable for local testing and private demos. It uses `db.sqlite3`
and does not require database setup.

The SQLite file location can be changed with:

```env
SQLITE_DATABASE_PATH=/var/data/db.sqlite3
```

For real payroll data, use PostgreSQL. It is safer for concurrent users,
backups, and production reliability.

Production `.env` example:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
DATABASE_URL=postgres://user:password@host:5432/database_name
```

DBeaver can connect using the same host, database, username, and password.

## Render Deployment Notes

Render is an internal deployment option, not a client requirement.

Recommended production setup on Render:

1. Create a PostgreSQL database in Render.
2. Create a Web Service from the GitHub repository.
3. Use build command:
   ```bash
   pip install -r requirements/production.txt && python manage.py collectstatic --no-input
   ```
4. Use start command:
   ```bash
   gunicorn config.wsgi:application
   ```
5. Add environment variables in Render dashboard.
6. Run migrations:
   ```bash
   python manage.py migrate
   ```
7. Create a superadmin:
   ```bash
   python manage.py createsuperuser
   ```

Important: uploaded Excel files in `salary_uploads/` need persistent storage if
they must survive redeploys. Render's normal app filesystem is not enough for
long-term payroll document storage.

SQLite on Render should only be used for a temporary private demo. To keep demo
data across deploys:

1. In the Render Web Service settings, add a persistent disk.
2. Use mount path:
   ```text
   /var/data
   ```
3. Set environment variable:
   ```env
   SQLITE_DATABASE_PATH=/var/data/db.sqlite3
   ```
4. Run migrations after the first deploy:
   ```bash
   python manage.py migrate
   ```

Without a persistent disk, the SQLite database will be lost on redeploys.

## Vercel Deployment Notes

Vercel is possible for a private demo, but it is serverless. Use PostgreSQL
there; do not use SQLite for payroll data on Vercel.

Project settings:

```text
Framework Preset: Other
Build Command: python manage.py collectstatic --noinput --settings=config.settings.vercel
Output Directory: leave blank
Run Command: leave blank
```

Required Vercel environment variables:

```env
DJANGO_SETTINGS_MODULE=config.settings.vercel
SECRET_KEY=<generated-secret>
ALLOWED_HOSTS=.vercel.app,<your-custom-domain>
CSRF_TRUSTED_ORIGINS=https://*.vercel.app,https://<your-custom-domain>
DATABASE_URL=<postgres-connection-url>
ADMIN_URL=management-portal/
COMPANY_NAME=Syntax Asia
CURRENCY_SYMBOL=LKR
SITE_URL=https://<your-vercel-domain>
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-app-password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Syntax Asia Payroll <smtp-user>
```

Database setup:

1. In Vercel, open the project.
2. Go to Storage.
3. Add a PostgreSQL database, or connect an external PostgreSQL provider.
4. Confirm `DATABASE_URL` is available to the project.
5. Run migrations from a machine with the same environment values:
   ```bash
   python manage.py migrate --settings=config.settings.vercel
   ```
6. Create the first admin user:
   ```bash
   python manage.py createsuperuser --settings=config.settings.vercel
   ```

The local `.env` file is not uploaded to Vercel. Add each value in Vercel's
Environment Variables screen. Keep `.env` only for local development.

Important limitation: uploaded salary Excel files are not durable on Vercel's
function filesystem. For a production Vercel deployment, move uploaded files to
object storage before using it with real payroll data.

## Future MFA Option

The product requirements do not ask for authenticator-app login. Keep it out of
the active product unless the client asks for stronger admin login security.

If enabled later, the implementation should:

- Add `django-otp` and `qrcode` back to the requirements.
- Register `django_otp`, `django_otp.plugins.otp_totp`, and
  `django_otp.plugins.otp_static` in installed apps.
- Keep normal email/password login.
- Add an authenticator-app setup screen for admin users.
- Require a 6-digit code after password login for staff and superadmin accounts.
- Add backup recovery codes for lost phones.
- Document the recovery process for HR or the system owner.

## Tests

Run all tests:

```bash
python -m pytest -q
```

Run Django checks:

```bash
python manage.py check
python manage.py check --deploy
```
