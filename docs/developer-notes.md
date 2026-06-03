# Developer Notes

Internal engineering notes for setup, deployment options, and implemented
features that are intentionally not described in the client-facing README.

## Local Setup

For the shortest current setup path, use `docs/running-guide.md`.

```bash
git clone <repo-url>
cd payroll_system

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements/development.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8004
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
SITE_URL=http://localhost:8004
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

## cPanel Deployment Notes

Use `docs/cpanel-deployment.md` for the Namecheap/cPanel deployment flow. This
branch is for cPanel deployment; keep other hosting providers in their own
deployment branches.

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
