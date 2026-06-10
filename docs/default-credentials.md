# Default Admin Credentials

The default/demo admin credential is defined in:

```text
payroll/management/commands/seed_default_users.py
```

It is created or reset only when this command is run:

```bash
python manage.py seed_default_users --settings=config.settings.cpanel
```

On cPanel without Terminal, upload and run this script from Python App's
`Execute python script` field:

```text
cpanel_seed_default_users.py
```

## Admin Portal

```text
URL: https://pay.syntaxasia.digital/management-portal/
Username: admin
Email: admin@example.com
Password: SyntaxAdmin#2026!
```

This credential is for deployment smoke tests only. Rotate it immediately
after handover and before entering real payroll data.

The seed command does not create employee accounts. Create employees manually
from the admin portal; the application will create employee login accounts from
those employee records.
