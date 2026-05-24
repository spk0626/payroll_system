# Syntax Asia — Salary Management System

A secure, multi-user web application that fully digitises employee payroll management. Administrators upload monthly Excel salary sheets; employees log in to view and print their payslips.

---

## Table of contents

- [What this system does](#what-this-system-does)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Architecture overview](#architecture-overview)
- [Data models](#data-models)
- [Security design](#security-design)
- [Getting started — local development](#getting-started--local-development)
- [Environment variables reference](#environment-variables-reference)
- [Running tests](#running-tests)
- [Deliverables roadmap](#deliverables-roadmap)
- [Production deployment](#production-deployment)
- [Common tasks](#common-tasks)

---

## What this system does

| Who | Can do |
|-----|--------|
| **Superadmin** | Everything — manage admin accounts, full audit access |
| **Staff admin** | Manage employees, upload salary sheets, send email notifications |
| **Employee** | Log in, view their own payslips, print to A4 |

Core capabilities:

- **Employee management** — create employees with auto-generated login accounts, manage branches and salary categories, bulk-assign employees to categories
- **Excel salary upload** — upload a monthly `.xlsx` sheet per category; system parses it, shows a diff preview, and upserts records atomically
- **Dynamic salary components** — no hardcoded salary fields; component names come from the Excel file itself each month
- **Employee self-service portal** — personal dashboard listing all payslip months; clean payslip detail view; guaranteed single A4 page on print
- **Email notifications** — one-click bulk send of branded HTML payslip emails; per-employee retry on failure
- **Security** — TOTP MFA for admins, rate-limited login, UUID-based payslip URLs (IDOR prevention), session idle timeout, full HTTP security headers

---

## Tech stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.12 |
| Framework | Django | 5.1.4 |
| Database | PostgreSQL (prod) / SQLite (dev) | PG 16 |
| Excel parsing | pandas + openpyxl | 2.2.3 / 3.1.5 |
| Frontend | Bootstrap 5 | 5.3 |
| MFA | django-otp | 1.5.4 |
| Rate limiting | django-ratelimit | 4.1.0 |
| Config | python-decouple | 3.8 |
| Web server | Nginx + Gunicorn | — |

---

## Project structure

```
syntax_asia/
│
├── config/                     # Django project config (not an app)
│   ├── settings/
│   │   ├── base.py             # Shared settings — all environments inherit this
│   │   ├── development.py      # SQLite, console email, DEBUG=True
│   │   └── production.py       # PostgreSQL, SMTP, strict security headers
│   ├── urls.py                 # Root URL config — admin at custom path
│   ├── wsgi.py
│   └── asgi.py
│
├── core/                       # Shared utilities — belongs to no single app
│   ├── constants.py            # All magic values live here (BatchStatus, MONTHS, etc.)
│   ├── context_processors.py   # Injects COMPANY_NAME, CURRENCY_SYMBOL into all templates
│   ├── mixins.py               # EmployeeRequiredMixin, StaffRequiredMixin
│   └── validators.py           # Excel file validator (extension + magic bytes + size)
│
├── accounts/                   # Authentication app
│   ├── urls.py                 # login, logout, password-reset, change-password (D2)
│   └── views.py                # Rate-limited login, session timeout, MFA (D2)
│
├── employees/                  # Employee data app
│   ├── models.py               # Branch, EmployeeCategory, Employee
│   ├── signals.py              # post_save → auto-create User + send welcome email
│   ├── admin.py                # Customised admin: bulk assign, password reset, filters
│   └── apps.py                 # Registers signals via ready()
│
├── payroll/                    # Salary processing app
│   ├── models.py               # PaySheet (UUID PK), UploadBatch, EmailLog
│   ├── admin.py                # Upload history, paysheet edit, email log views
│   ├── urls.py                 # Employee portal URLs (D3)
│   └── views.py                # Dashboard, payslip detail, print view (D3)
│
├── templates/
│   ├── accounts/email/
│   │   └── welcome.txt         # Welcome email sent on employee account creation
│   ├── payroll/                # Portal templates (D3)
│   └── email/                  # HTML payslip notification template (D5)
│
├── static/
│   ├── css/                    # main.css, print.css (D3)
│   ├── js/                     # session-timeout.js (D2)
│   └── img/                    # Company logo
│
├── tests/
│   ├── employees/
│   │   └── test_models.py      # 14 tests: models, signals, password generator
│   ├── accounts/               # Auth tests (D2)
│   └── payroll/                # Parser, IDOR, email tests (D3–D5)
│
├── requirements/
│   ├── base.txt                # Pinned production dependencies
│   ├── development.txt         # Adds pytest, coverage, debug-toolbar
│   └── production.txt          # Adds gunicorn
│
├── deploy/                     # Nginx config, systemd service, backup script (D8)
├── salary_uploads/             # Excel files stored here — NOT web-accessible
├── .env.example                # Template for all required environment variables
├── .gitignore
├── pytest.ini
└── manage.py
```

### Why this structure

**`config/` is not an app.** It holds only project-level config and routing. No models, no views, no business logic.

**`core/` has no models.** If a utility needs a model, it belongs in an app. `core/` is pure logic and shared tools that apps import from.

**Three app boundary rule.** `accounts` owns auth. `employees` owns people data. `payroll` owns salary data. No app imports from another app's `models.py` at module level — only string FK references (`"employees.Employee"`) or lazy imports inside functions.

**`tests/` mirrors the app structure.** Each app's tests live in `tests/<appname>/`, not inside the app directory. This keeps test code completely separate from production code and makes coverage analysis straightforward.

---

## Architecture overview

```
Browser (HTTPS)
      │
      ▼
  Nginx                    ← serves /static/ directly; proxies everything else
      │
      ▼
  Gunicorn (4 workers)
      │
      ├── Admin interface  ← /management-portal/  (custom URL, staff + TOTP only)
      │
      └── Employee portal  ← /portal/             (login required, owns-payslip check)
              │
              ├── accounts app   (login, MFA, password reset)
              ├── employees app  (employee + category + branch management)
              └── payroll app    (upload engine, portal views, email sender)
                      │
                      ├── PostgreSQL   (all data including JSON salary breakdowns)
                      ├── salary_uploads/  (Excel files, outside web root)
                      └── SMTP         (welcome emails, payslip notifications)
```

**Request flow for a payslip view:**
1. Employee hits `/portal/payslip/<uuid>/`
2. `LoginRequiredMixin` checks session — redirects to login if expired
3. `EmployeeRequiredMixin` checks `request.user.employee` exists
4. View fetches `PaySheet` by UUID
5. **Ownership check:** `if paysheet.employee.user != request.user → 403` — this runs even though UUIDs are unguessable; defence in depth
6. Template renders breakdown JSON as a table; print CSS ensures A4 single-page output

---

## Data models

### `employees` app

**`Branch`** — managed list of company branches. Stored as a model (not free text) to prevent inconsistent data. `PROTECT` prevents deletion of a branch with employees.

**`EmployeeCategory`** — payroll groupings (e.g. Permanent Staff, Contract Workers). Each category gets its own monthly Excel upload with its own salary components.

**`Employee`** — core record. Key fields:
- `employee_number` — business identifier used in Excel uploads; must match exactly
- `user` — `OneToOneField` to Django's `User`; created automatically by signal
- `must_change_password` — `True` on creation; clears when employee changes their initial password
- `is_active` — soft-delete flag; never hard-delete employees

### `payroll` app

**`PaySheet`** — one employee's salary for one month.
- Primary key is a **UUID** — used in all employee-facing URLs to prevent IDOR attacks
- `breakdown` is a `JSONField`: `{"Basic Salary": "50000.00", "HRA": "5000.00", ...}`
- `category_snapshot` is set at upload time and never changes, preserving historical accuracy
- `gross_total` is computed and stored at upload time (no recalculation on every render)
- Unique constraint on `(employee, month, year)`

**`UploadBatch`** — audit record for every Excel file upload. Records filename, who uploaded it, processing warnings, counts of created/updated/skipped records.

**`EmailLog`** — one record per employee per email send attempt. Enables retry of failed sends without re-sending to successful recipients.

### Key database indexes

| Index | Purpose |
|-------|---------|
| `(employee, month, year)` on PaySheet | Fast employee portal lookups |
| `(month, year, category_snapshot)` on PaySheet | Admin batch views |
| `(month, year, category)` on UploadBatch | Upload history filter |
| `(status, batch_sent_at)` on EmailLog | Retry failed emails |
| `(employee_number)` on Employee | Excel parser lookups |

---

## Security design

| Threat | Mitigation |
|--------|-----------|
| IDOR — employee views another's payslip | UUID primary keys + ownership check on every view |
| Brute force login | `django-ratelimit`: 5 attempts / 15 min per IP |
| Admin account compromise | TOTP MFA via `django-otp` (mandatory for superadmin) |
| Malicious Excel upload | MIME + magic-byte validation, 5 MB cap, stored outside web root |
| Formula injection in Excel | Cells starting with `=`, `+`, `-`, `@` stripped before parsing |
| Session hijack via unattended browser | 30-minute idle auto-logout |
| Admin panel discovery by bots | Admin URL is a custom path from env var, not `/admin/` |
| Salary data in server logs | `LOG_LEVEL=WARNING` in production; no request body logging |
| Dependency vulnerabilities | Pinned versions in `requirements/base.txt`; `pip-audit` in CI |
| Weak initial passwords | Cryptographically random 14-char password via `secrets` module |

All Django security defaults are active: CSRF middleware, XSS-safe template auto-escaping, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.

Production adds: HSTS (1 year), `Secure` and `HttpOnly` session cookies, `SameSite=Lax`, SSL redirect.

---

## Getting started — local development

### Prerequisites

- Python 3.12
- `libmagic` system library (for file type detection)

```bash
# macOS
brew install libmagic

# Ubuntu / Debian
sudo apt-get install libmagic1
```

### 1. Clone and create a virtual environment

```bash
git clone <repository-url>
cd syntax_asia

python3.12 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements/development.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

The development defaults in `.env.example` work out of the box for local development with SQLite. The only value you must set is `SECRET_KEY`:

```bash
# Generate a secure key
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Paste the output as the value of `SECRET_KEY` in `.env`.

### 4. Run database migrations

```bash
python manage.py migrate
```

This creates a local `db.sqlite3` file. No database setup is required for development.

### 5. Create a superadmin account

```bash
python manage.py createsuperuser
```

You will be prompted for a username (use an email address), email, and password.

### 6. Create the salary uploads directory

```bash
mkdir -p salary_uploads
```

This directory stores uploaded Excel files. It is listed in `.gitignore` and must never be served by a web server.

### 7. Start the development server

```bash
python manage.py runserver
```

### 8. Access the application

| URL | What it is |
|-----|-----------|
| `http://localhost:8000/management-portal/` | Admin panel (superadmin login) |
| `http://localhost:8000/` | Employee login page |
| `http://localhost:8000/portal/` | Employee dashboard (after login) |

> The admin URL path is configured by the `ADMIN_URL` environment variable. Default for development is `management-portal/`.

---

## Environment variables reference

All variables are read from the `.env` file via `python-decouple`. No environment variable has a hardcoded secret default — the application will raise an error on startup if a required variable is missing.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DJANGO_SETTINGS_MODULE` | Yes | — | `config.settings.development` or `config.settings.production` |
| `SECRET_KEY` | Yes | — | 64+ character random string. Generate with `secrets.token_urlsafe(64)` |
| `DEBUG` | Yes | — | `True` for development, `False` for production |
| `ALLOWED_HOSTS` | Yes | `localhost` | Comma-separated list of valid hostnames |
| `DATABASE_URL` | Prod only | SQLite | Full PostgreSQL URL: `postgres://user:pass@host:5432/dbname` |
| `ADMIN_URL` | No | `management-portal/` | Custom path for the admin panel. Change this in production |
| `EMAIL_HOST` | No | `smtp.gmail.com` | SMTP server hostname |
| `EMAIL_PORT` | No | `587` | SMTP port (587 for TLS, 465 for SSL) |
| `EMAIL_HOST_USER` | Prod only | — | SMTP authentication username |
| `EMAIL_HOST_PASSWORD` | Prod only | — | SMTP password or app-specific password |
| `EMAIL_USE_TLS` | No | `True` | Always `True` in production |
| `DEFAULT_FROM_EMAIL` | No | `noreply@syntaxasia.lk` | From address on all outgoing emails |
| `COMPANY_NAME` | No | `Syntax Asia` | Shown in payslip header and email templates |
| `COMPANY_ADDRESS` | No | — | Shown in payslip header |
| `CURRENCY_SYMBOL` | No | `LKR` | Currency code shown on payslips and in the admin |
| `SESSION_IDLE_TIMEOUT` | No | `1800` | Seconds before idle session is terminated (30 minutes) |
| `EXCEL_UPLOAD_MAX_MB` | No | `5` | Maximum Excel file upload size in megabytes |
| `EXCEL_MAX_ROWS` | No | `500` | Maximum rows allowed in Column A of an uploaded sheet |
| `ADMINS_EMAIL` | Prod only | — | Email address that receives Django 500 error notifications |

---

## Running tests

```bash
# Run all tests
python -m pytest

# Run with coverage report
python -m pytest --cov=. --cov-report=term-missing

# Run a specific test file
python -m pytest tests/employees/test_models.py -v

# Run a specific test class
python -m pytest tests/employees/test_models.py::TestEmployeeSignal -v
```

Current test status: **14 tests, all passing** (Deliverable 1).

### Test coverage by deliverable

| Deliverable | Test file | Coverage focus |
|-------------|-----------|---------------|
| D1 (current) | `tests/employees/test_models.py` | Models, signal, password generator, soft-delete, uniqueness constraints |
| D2 | `tests/accounts/` | Login rate limiting, TOTP flow, session timeout, password reset |
| D3 | `tests/payroll/test_views.py` | IDOR prevention, ownership check, portal access control |
| D4 | `tests/payroll/test_parser.py` | All 9+ Excel edge cases, diff engine, atomic rollback |
| D5 | `tests/payroll/test_email.py` | Per-email failure handling, retry logic, email log accuracy |

---

## Deliverables roadmap

The project is built across 8 sequential deliverables. Each deliverable is a working, tested increment.

| # | Name | Days | Status | Key additions |
|---|------|------|--------|---------------|
| **D1** | Foundation | 1–4 | ✅ Complete | Project scaffold, models, migrations, admin, signals, 14 tests |
| **D2** | Auth & access control | 5–9 | Pending | Login with rate limiting, TOTP MFA, session timeout, password reset |
| **D3** | Employee portal | 10–14 | Pending | Dashboard, payslip detail (UUID URLs), A4 print CSS, IDOR tests |
| **D4** | Excel upload engine | 15–22 | Pending | File validation, pandas parser, diff preview, atomic upsert |
| **D5** | Email notifications | 23–27 | Pending | HTML email template, bulk send, EmailLog, per-employee retry |
| **D6** | Admin polish | 28–30 | Pending | Upload history, manual paysheet edit, bulk actions, audit log |
| **D7** | Security hardening | 31–33 | Pending | HTTP headers, IDOR tests, custom error pages, pip-audit |
| **D8** | Deploy & handover | 34–35 | Pending | Nginx config, systemd service, SSL, backup script, UAT |

---

## Production deployment

> Full deployment runbook is in `deploy/RUNBOOK.md` (added in D8). The summary below covers the key steps.

### Server requirements

- Ubuntu 24.04 LTS
- 2 vCPU, 2 GB RAM minimum (DigitalOcean Droplet or Hetzner CX22 — ~$12–18/month)
- PostgreSQL 16
- Python 3.12

### Quick steps

```bash
# 1. Install system packages
sudo apt-get install python3.12 python3.12-venv nginx postgresql libmagic1 certbot python3-certbot-nginx

# 2. Set up PostgreSQL
sudo -u postgres createuser syntax_user
sudo -u postgres createdb syntax_asia_db -O syntax_user

# 3. Clone, install, configure
git clone <repo> /var/www/syntax_asia
cd /var/www/syntax_asia
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/production.txt

# 4. Set environment variables in .env (copy from .env.example)
# Set DJANGO_SETTINGS_MODULE=config.settings.production
# Set all required variables — see reference table above

# 5. Initialise
python manage.py migrate
python manage.py collectstatic --no-input
python manage.py createsuperuser

# 6. Set up Nginx, Gunicorn systemd service, SSL
# (full configs provided in deploy/)

# 7. Obtain SSL certificate
sudo certbot --nginx -d yourdomain.lk
```

### Critical production checklist

- [ ] `DEBUG=False` in `.env`
- [ ] `SECRET_KEY` is a fresh 64+ character random string
- [ ] `ADMIN_URL` is changed from `management-portal/` to something unique
- [ ] `salary_uploads/` directory is **not** served by Nginx
- [ ] `SECURE_HSTS_SECONDS=31536000` is set (via production settings)
- [ ] Daily `pg_dump` cron job is configured
- [ ] `ADMINS_EMAIL` is set so 500 errors are reported
- [ ] Superadmin TOTP MFA is enrolled after first login

---

## Common tasks

### Create a new admin account

```bash
python manage.py createsuperuser
```

Or from the admin panel: log in as superadmin → Users → Add user → check "Staff status".

### Reset an employee's password

Admin panel → Employees → select employee(s) → Actions → "Reset passwords for selected employees". The new password is emailed to the employee automatically.

### Process a monthly salary sheet

Admin panel → Upload batches → Add → select month, year, category, upload `.xlsx` file → review diff preview → confirm.

### Retry failed payslip emails

Admin panel → Email logs → filter by Status = Failed → select all → Actions → Retry (added in D5).

### Run database backup manually

```bash
pg_dump -U syntax_user syntax_asia_db > backup_$(date +%Y%m%d).dump
```

### Check for dependency vulnerabilities

```bash
pip install pip-audit
pip-audit -r requirements/base.txt
```

### Purge old Excel upload files (12-month retention)

```bash
python manage.py purge_old_uploads   # management command added in D6
```

---

## Decisions log

Key engineering decisions made during design, and why.

| Decision | Why |
|----------|-----|
| UUID primary key on PaySheet | Sequential integer IDs allow IDOR attacks — employee 43 can guess `/payslip/42/` |
| Soft-delete only on employees | Payroll records are financial evidence; must survive employee departure |
| Signal for user account creation | Keeps `save()` clean; signal can be disconnected for bulk imports; independently testable |
| `PROTECT` on Branch → Employee FK | Prevents accidental branch deletion cascading to employee records |
| `category_snapshot` on PaySheet | Category reassignment must not retroactively alter historical paysheets |
| Split settings (base/dev/prod) | One environment variable switches the entire configuration; no accidental production settings in dev |
| `core/constants.py` | Every magic string and number in one file; grep-able; no scattered hardcoded values |
| `salary_uploads/` outside `MEDIA_ROOT` | Excel files contain all employees' salaries; must never be accidentally served by Nginx |
| Last-wins for duplicate employee columns | Mirrors Excel behaviour; warning always surfaced to admin |
| Explicit diff preview on re-upload | No silent deletes of salary records; admin always aware of what will change |

---

## Licence

Private — Syntax Asia internal use only. Not for distribution.