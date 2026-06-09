# cPanel Deployment

Use this guide on `feature/cpanel-deployment` for
`https://pay.syntaxasia.digital`.

## Branches

- cPanel: `feature/cpanel-deployment`
- Vercel: `feature/vercel-deployment`

Keep provider-specific settings, startup files, and docs on their own branch.

## cPanel App

In cPanel Python App:

```text
Python version: 3.6.15
Application root: /pay.syntaxasia.digital
Application URL: pay.syntaxasia.digital
Startup file: passenger_wsgi.py
Application entry point: application
```

Create a MySQL database and user in cPanel, then grant the user all
privileges on the database.

Set environment variables:

```env
DJANGO_SETTINGS_MODULE=config.settings.cpanel
SECRET_KEY=<generated-production-secret>
DEBUG=False
ALLOWED_HOSTS=pay.syntaxasia.digital
CSRF_TRUSTED_ORIGINS=https://pay.syntaxasia.digital
DATABASE_URL=mysql://<user>:<password>@localhost:3306/<database>
ADMIN_URL=management-portal/
SITE_URL=https://pay.syntaxasia.digital
COMPANY_NAME=Syntax Asia
CURRENCY_SYMBOL=LKR
```

If cPanel shows a database host other than `localhost`, use that host in
`DATABASE_URL`.

## SQLite Backup Import

Export the latest SQLite backup locally:

```powershell
$env:SQLITE_DATABASE_PATH="C:\Sandali\payroll_system\backups\db_20260602_174558_before_paysheet_admin_fix.sqlite3"
.\.venv\Scripts\python.exe manage.py dumpdata --settings=config.settings.development --natural-foreign --natural-primary -e contenttypes -e auth.Permission -o C:\tmp\payroll_mysql_import.json
```

Upload `payroll_mysql_import.json` to the cPanel app root temporarily.

Run from cPanel Terminal or SSH:

```bash
pip install -r requirements/production.txt
python manage.py migrate --settings=config.settings.cpanel
python manage.py loaddata payroll_mysql_import.json --settings=config.settings.cpanel
python manage.py seed_default_users --settings=config.settings.cpanel
python manage.py collectstatic --noinput --settings=config.settings.cpanel
python manage.py check --deploy --settings=config.settings.cpanel
```

Delete `payroll_mysql_import.json` after import. It contains payroll and user
data.

## Initial Credentials

This deployment/demo admin credential is defined in
`payroll/management/commands/seed_default_users.py` and is created or reset only
after running:

```bash
python manage.py seed_default_users --settings=config.settings.cpanel
```

If cPanel Terminal is unavailable, upload and run this file from Python App's
`Execute python script` field after migrations:

```text
cpanel_seed_default_users.py
```

```text
Admin portal:
URL: https://pay.syntaxasia.digital/management-portal/
Username: admin
Email: admin@example.com
Password: SyntaxAdmin#2026!

```

The seed command does not create employee accounts. Create employees manually
from the admin portal; the application will create employee login accounts from
those employee records.

Rotate the demo password immediately after handover and before entering real
payroll data. See `docs/default-credentials.md`.
