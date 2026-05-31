# Syntax Asia Payroll System

A Django payroll management app for Syntax Asia. Staff admins manage employees,
upload monthly Excel salary sheets, send payslip email notifications, and review
audit history. Employees log in to view and print only their own payslips.

## Current Status

The core app features are implemented through the security hardening work:

- Employee and branch/category management
- Employee account creation, password reset, forced password change, and MFA support
- Employee portal with UUID payslip URLs and ownership checks
- Excel upload parser and upload audit records
- Payslip email notifications with failed-send retry
- Admin audit views and upload-file retention cleanup command
- Security headers, custom error pages, and rate-limited authentication

Deployment files and integration-test placeholders are still being prepared in
the current working tree and are not part of the committed app yet.

## Stack

- Python 3.12
- Django 5.1.4
- SQLite for local development
- PostgreSQL for production
- pandas and openpyxl for Excel parsing
- django-otp for admin MFA
- django-ratelimit for login protection
- python-decouple and dj-database-url for configuration
- Custom CSS and Django templates

## Quick Start

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

On macOS/Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

Generate a local `SECRET_KEY` if needed:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Default local URLs:

| URL | Purpose |
| --- | --- |
| `http://localhost:8000/` | Employee login |
| `http://localhost:8000/portal/` | Employee payslip dashboard |
| `http://localhost:8000/management-portal/` | Django admin portal |

The admin URL comes from `ADMIN_URL` and should be changed for production.

## Project Layout

```text
payroll_system/
├── accounts/              # Login, password reset, MFA, session middleware
├── config/                # Django settings, root URLs, error handlers
├── core/                  # Shared constants, validators, mixins, security headers
├── employees/             # Branches, categories, employees, account signals
├── payroll/               # Paysheets, uploads, parser, email service, portal views
│   ├── management/commands/
│   │   └── purge_old_uploads.py
│   └── services/
│       ├── email_service.py
│       ├── excel_parser.py
│       └── upload_service.py
├── requirements/          # Base, development, and production dependencies
├── static/                # Main and print CSS, JavaScript
├── templates/             # Page, email, and error templates
└── tests/                 # Pytest suite grouped by app/feature
```

## Environment

Configuration is read from `.env` via `python-decouple`.

Important values:

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Required Django secret |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` or `config.settings.production` |
| `ALLOWED_HOSTS` | Comma-separated allowed hostnames |
| `DATABASE_URL` | Production PostgreSQL connection URL |
| `ADMIN_URL` | Custom admin path, default `management-portal/` |
| `SITE_URL` | Base URL used in emails |
| `COMPANY_NAME` | Displayed in templates and emails; not hardcoded |
| `COMPANY_ADDRESS` | Optional payslip/company address |
| `CURRENCY_SYMBOL` | Currency label, default `LKR` |
| `EMAIL_*` | SMTP settings for production email delivery |
| `MEMCACHED_LOCATION` | Production cache for rate limiting |

In development, the email backend prints email content to the console. That
means temporary passwords and reset links will not arrive in a real inbox until
SMTP settings are configured in production.

## Main Workflows

### Employee Setup

1. Admin creates branches and employee categories.
2. Admin creates an employee.
3. The app creates a linked Django user automatically.
4. The employee receives or is shown a temporary password, then must change it.

### Excel Upload

1. Configure `CategoryParserConfig` for each employee category.
2. Upload the monthly `.xlsx` file for that category.
3. The parser reads employee numbers and salary component rows.
4. The upload service builds a create/update/absent diff.
5. Confirmed changes write `PaySheet` records and an `UploadBatch` audit record.

### Payslip Access

Employees can only access paysheets where `paysheet.employee.user == request.user`.
Payslip URLs use UUIDs, but the ownership check is still enforced on every detail
and print view.

### Email Notifications

Admins can send payslip notifications from upload batches. Every send attempt is
recorded in `EmailLog`, and failed sends can be retried without resending to
successful recipients.

## Tests

Run the suite:

```bash
python -m pytest -q
```

Current status on the security branch:

```text
91 passed
```

Useful focused commands:

```bash
python -m pytest tests/accounts/test_auth.py -q
python -m pytest tests/payroll/test_portal.py -q
python -m pytest tests/payroll/test_parser.py -q
python -m pytest tests/payroll/test_email_service.py -q
python -m pytest tests/payroll/test_admin.py -q
python -m pytest tests/test_security.py -q
```

Also run Django checks before pushing:

```bash
python manage.py check
python manage.py check --deploy
```

For `check --deploy`, use production-like environment variables and do not reuse
development secrets.

## Security Notes

- Admin is mounted at `ADMIN_URL`, not Django's default `/admin/`.
- Login is rate-limited.
- Admin MFA uses TOTP.
- Sessions use idle timeout and forced password-change flow.
- Payslip URLs use UUIDs and still enforce ownership checks.
- Uploaded Excel files are stored outside the web root in `salary_uploads/`.
- Parser blocks formula-injection prefixes except negative numbers used for deductions.
- Custom security middleware sets CSP, permissions policy, frame, referrer, and content-type headers.
- Production settings enable HTTPS redirect, HSTS, secure cookies, and PostgreSQL.

Salary and bank details are restricted personal data. Avoid logging request
bodies, Excel contents, payslip breakdowns, or generated passwords.

## Admin And Audit Tools

- `UploadBatch` records every upload attempt and processing result.
- `EmailLog` records payslip email send status per employee.
- Admin actions can send payslip notifications and retry failed sends.
- `python manage.py purge_old_uploads` deletes old uploaded Excel files while
  preserving the database audit record.

Example dry run:

```bash
python manage.py purge_old_uploads --months 12 --dry-run
```

## Production Checklist

- Set `DEBUG=False`.
- Use a fresh, strong `SECRET_KEY`.
- Set `ALLOWED_HOSTS`.
- Configure `DATABASE_URL` for PostgreSQL.
- Configure SMTP settings for real email delivery.
- Change `ADMIN_URL` from the development default.
- Ensure `salary_uploads/` is not served by Nginx or any static/media route.
- Run `python manage.py check --deploy`.
- Run the full test suite.
- Enroll MFA for admin accounts.
- Configure backups before go-live.

## Engineering Practices

- Keep changes small and reviewable.
- Prefer service modules for business logic that should be tested without HTTP.
- Keep salary data out of URLs, logs, and error messages.
- Add regression tests for every security or payroll-money behavior change.
- Run checks before each push and keep branch names feature-focused.

## License

Private - Syntax Asia internal use only.
