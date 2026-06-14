# Syntax Asia Payroll System

A web-based payroll system for Syntax Asia. Administrators manage employees,
upload monthly Excel salary sheets, send payslip notifications, and review upload
history. Employees log in to view and print their own payslips.

## Main Features

- Employee, branch, and employee category management
- Automatic employee login account creation
- Password reset and forced first-login password change
- Category-based Excel salary upload
- Dynamic salary components from Excel files
- Employee payslip dashboard, detail view, and A4 print view
- Payslip email notifications with retry for failed sends
- Upload history, email history, and admin audit views
- Security headers, rate-limited login, and custom error pages

## How To Run Locally

For first-time setup on Windows, use:

```bat
setup_first_time.bat
```

It creates `.venv` if missing, installs dependencies, applies migrations, and
runs Django checks. It does not delete the database.

After setup, start the server with:

```bat
run_payroll.bat
```

The app runs at:

```text
http://127.0.0.1:8004/
```

### First Time Setup

Run these commands from the project folder:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py check
```

Then start the app:

```bat
run_payroll.bat
```

Open:

```text
http://127.0.0.1:8004/
```

### Next Time

Use the batch file:

```bat
run_payroll.bat
```

`run_payroll.bat` does not create a virtual environment, install packages,
run migrations, seed data, or create a new database. It only starts the existing
app environment.

You can also run the server directly:

```bat
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8004
```

Keep the terminal window open while using the app. Press `Ctrl+C` to stop the
server.

## User Manual

### Admin Login

1. Open the admin portal:
   ```text
   /management-portal/
   ```
2. Sign in with a staff or superadmin account.
3. Superadmins can manage other admin users from Admin accounts.

### Branches And Employee Categories

Create branches and employee categories before adding employees.

Employee categories are groups such as:

- Permanent staff
- Contract workers
- Management
- Any other payroll grouping used by the company

Each employee belongs to one category at a time. Categories are used to group
employees for payroll uploads and filtering.

### Adding Employees

1. Go to Employees.
2. Add employee number, full name, email, branch, category, bank details, and
   date of joining.
3. Save.
4. The system automatically creates a login user using the employee email.
5. The employee must change their temporary password on first login.

If an employee cannot log in, use the admin action to reset their password.

### Uploading Salary Sheets

1. Go to Payroll -> Upload batches.
2. Click `Upload salary sheet`.
3. Select category, month, year, and the `.xlsx` file.
4. Submit the upload.
5. The system parses the file, creates or updates paysheets, and shows a table
   of processed paysheets.

Salary sheet format:

- Row 1 contains employee numbers from column B onward.
- Column A contains salary row labels such as Basic, Allowance, or Deduction.
- Rows below row 1 are treated as dynamic salary rows.

Unknown employee numbers are skipped and shown as warnings. Existing paysheets
for the same month are updated instead of duplicated. Admins can download the
processed batch as CSV for Excel.

### Employee Portal

Employees log in from:

```text
/
```

After login, they can:

- View available payslip months
- Open a salary breakdown
- Print or save the payslip as PDF

Employees can only view their own payslips.

### Email Notifications

After salary upload, admins can send payslip emails from Upload batches.

The system records each send attempt in Email logs:

- Sent
- Failed
- Pending

Failed emails can be retried without resending successful emails.

## Security Notes

- Admin URL is configurable and should not stay as the default in production.
- Employee payslip URLs use UUIDs and ownership checks.
- Uploaded salary files are stored outside public static/media paths.
- Login is rate-limited.
- Salary and bank details should not be logged or shared through screenshots.

## Developer Docs

- `docs/running-guide.md` - local run commands and cPanel setup checklist.
- `docs/default-credentials.md` - demo credential source and cPanel seed script.
- `docs/agent-handoff.md` - short project map for AI-assisted work.
- `docs/release-checklist.md` - branch and release checks before pushing.

## License

Private - Syntax Asia internal use only.
