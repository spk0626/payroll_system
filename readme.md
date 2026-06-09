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

## User Manual

### Admin Login

1. Open the admin portal:
   ```text
   /management-portal/
   ```
2. Sign in with a staff or superadmin account.
3. Superadmins can manage other admin users from Django's Users section.

### Branches And Employee Categories

Create branches and employee categories before adding employees.

Employee categories are groups such as:

- Permanent staff
- Contract workers
- Management
- Any other payroll grouping used by the company

Each employee belongs to one category at a time. Categories matter because
different categories may use different Excel salary formats.

### Category Parser Configs

`CategoryParserConfig` tells the system how to read an Excel sheet for one
employee category.

In client-facing language:

> A parser config is the salary-sheet reading rule for a category. It tells the
> system which row contains employee numbers and which rows are only information
> rows, so the remaining rows can be treated as salary components.

Example:

| Field | Example | Meaning |
| --- | --- | --- |
| Category | Permanent Staff | The employee group this rule applies to |
| Employee ID row label | Employee | The label in column A for the row containing employee numbers |
| Fixed info row labels | `["Employee Name", "Designation"]` | Rows to ignore because they are not salary amounts |

Keep `CategoryParserConfig`. It is useful because it lets Syntax Asia change
Excel formats by category without changing code.

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
5. The system parses the file, creates or updates paysheets, and records warnings.

Unknown employee numbers are skipped and shown as warnings. Existing paysheets
for the same month are updated instead of duplicated.

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
