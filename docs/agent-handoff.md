# Agent Handoff Guide

Use this file to reduce token usage when working with AI coding agents.

## Project Shape

This is a Django payroll system.

Main areas:

- `accounts/` - login, logout, password reset, password changes, session rules.
- `employees/` - employee, branch, and category models/admin behavior.
- `payroll/` - salary uploads, Excel parsing, payslips, emails, portal views.
- `config/settings/` - environment-specific Django settings.
- `templates/` - Django templates for auth, admin overrides, portal, emails.
- `static/css/` - shared, portal, admin, and print styles.
- `tests/` - pytest/Django tests grouped by app.

## High-Signal Files

Read these first for most tasks:

- `readme.md` for user-facing behavior.
- `docs/running-guide.md` for local setup and checks.
- `docs/developer-notes.md` for deployment and internal notes.
- `config/settings/base.py` before changing installed apps, middleware, storage,
  auth, static files, or upload limits.
- `payroll/services/upload_service.py` and `payroll/services/excel_parser.py`
  before changing salary uploads.
- `tests/accounts/test_auth.py` before changing login/password/session behavior.
- `tests/payroll/test_admin.py` and `tests/payroll/test_portal.py` before
  changing payroll admin or portal behavior.

## Token-Saving Workflow

1. Start with `git status --short --branch`.
2. Use `rg` to find the exact symbols or routes involved.
3. Read only the nearest view/model/service/template/test files.
4. Make the smallest change that fixes the root cause.
5. Run focused tests first, then broader tests only when shared behavior changed.
6. Summarize changed files, commands run, and remaining risk.

Avoid pasting full files into prompts. Point agents to filenames and line
numbers, then ask for a focused fix.

## Branch Rules

Keep feature and deployment work separate:

- Deployment-only changes go on `feature/vercel-deployment`.
- Parked or experimental features must stay on their own feature branch.
- Do not merge parked feature branches into deployment branches.
- Before pushing a deployment branch, search for parked feature keywords.

Current parked feature note:

- Authenticator-app MFA/OTP is not part of the active product.
- Active branches should not include `django-otp`, `qrcode`, `MFASetupView`,
  `mfa/setup/`, or `templates/accounts/mfa_setup.html`.
- If MFA is needed later, implement it on a dedicated branch and include backup
  recovery codes and admin recovery documentation.

## Useful Commands

```powershell
git status --short --branch
rg -n "MFA|mfa|OTP|otp|django_otp|qrcode|TOTP|mfa/setup"
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe -m pytest tests\accounts\test_auth.py -q
```

