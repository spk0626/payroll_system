"""
System-wide constants.

Centralised here so magic values never appear scattered through the codebase.
Import from here — never define constants inline in views or models.
"""

# ─── Employee ──────────────────────────────────────────────────────────────────
EMPLOYEE_NUMBER_MAX_LENGTH = 20
EMPLOYEE_NAME_MAX_LENGTH = 150
BANK_NAME_MAX_LENGTH = 100
BANK_ACCOUNT_NAME_MAX_LENGTH = 150
BANK_BRANCH_NAME_MAX_LENGTH = 100
BRANCH_NAME_MAX_LENGTH = 100
CATEGORY_NAME_MAX_LENGTH = 100

# ─── Payroll ───────────────────────────────────────────────────────────────────
SALARY_COMPONENT_MAX_LENGTH = 200
GROSS_TOTAL_MAX_DIGITS = 12
GROSS_TOTAL_DECIMAL_PLACES = 2

# Months (used in payroll forms and display)
MONTHS = [
    (1, "January"), (2, "February"), (3, "March"),
    (4, "April"), (5, "May"), (6, "June"),
    (7, "July"), (8, "August"), (9, "September"),
    (10, "October"), (11, "November"), (12, "December"),
]

# ─── Upload batch status ───────────────────────────────────────────────────────
class BatchStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"

    CHOICES = [
        (PENDING, "Pending"),
        (PROCESSING, "Processing"),
        (DONE, "Done"),
        (FAILED, "Failed"),
    ]

# ─── Email log status ──────────────────────────────────────────────────────────
class EmailStatus:
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

    CHOICES = [
        (PENDING, "Pending"),
        (SENT, "Sent"),
        (FAILED, "Failed"),
    ]

# ─── Excel parsing ─────────────────────────────────────────────────────────────
# Cells starting with these characters are treated as formula injection attempts.
FORMULA_INJECTION_PREFIXES = ("=", "+", "-", "@")

# The first column (Column A) contains salary component labels.
COMPONENT_COLUMN_INDEX = 0

# Employee numbers are in row 0 (the first row) of employee columns.
EMPLOYEE_NUMBER_ROW_INDEX = 0