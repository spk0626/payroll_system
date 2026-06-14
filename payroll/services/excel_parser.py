"""
Excel salary sheet parser.

Reads an uploaded .xlsx file and returns a structured ParseResult.
No Django model writes happen here — this is pure data transformation.
The upload view handles database operations using the ParseResult.

Design:
  - HR-friendly default: first row contains employee numbers, column A contains
    dynamic payroll row labels below it.
  - Defensive: every edge case is handled explicitly with a warning,
    not an exception. The caller always gets a result even if partial.
  - No side effects: this function reads; it never writes to DB or disk.

Edge cases handled:
  1.  Employee number with whitespace → stripped
  2.  Employee number stored as float by Excel (1.0 → "1")
  3.  Merged cells / NaN employee columns → skipped with warning
  4.  Blank component name rows → skipped silently
  5.  Amount stored as string with commas ("50,000" → 50000)
  6.  Formula injection via string prefix (+50000, @cmd) → zero + warning
      Note: actual cell formulas (=SUM()) read as NaN by pandas/openpyxl
      and are treated as zero/blank without a separate warning.
  7.  Amount that cannot be parsed (e.g. "N/A") → zero + warning
  8.  Duplicate employee number in same sheet → last column wins + warning
  9.  Employee number not in DB → skipped with warning
  10. ID row label not found in sheet → fatal ParseError
  11. File has only one column (no employee columns) → warning, empty result
  12. Negative amounts (deductions) → allowed, stored as-is
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Set, Tuple

import pandas as pd

from core.constants import FORMULA_INJECTION_PREFIXES

logger = logging.getLogger(__name__)

# Injection prefixes that are NOT the minus sign.
# Negative numbers like -5000 are valid salary values (deductions).
# We only guard against =, +, @ which are formula injection vectors.
_INJECTION_PREFIXES = tuple(p for p in FORMULA_INJECTION_PREFIXES if p != "-")


# ─── Result types ─────────────────────────────────────────────────────────────

@dataclass
class EmployeeRecord:
    """Parsed salary data for one employee column."""
    employee_number: str
    breakdown: Dict[str, Decimal]
    gross_total: Decimal


@dataclass
class ParseResult:
    records: List[EmployeeRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def has_fatal_errors(self) -> bool:
        return bool(self.errors)


# ─── Parser ───────────────────────────────────────────────────────────────────

def parse_salary_sheet(
    file_path: str,
    emp_id_row_label: str = None,
    fixed_info_row_labels: List[str] = None,
    known_employee_numbers: Set[str] = None,
) -> ParseResult:
    result = ParseResult()
    fixed_info_row_labels = fixed_info_row_labels or []
    known_employee_numbers = known_employee_numbers or set()

    # 1. Read file
    try:
        df = pd.read_excel(
            file_path,
            sheet_name=0,
            header=None,
            dtype=str,
            keep_default_na=False,
            engine="openpyxl",
        )
    except Exception as exc:
        result.errors.append(f"Could not read file: {exc}")
        return result

    if df.empty:
        result.errors.append("The uploaded file is empty.")
        return result

    # 2. Find employee ID row.
    # New uploads use row 1. The labelled-row path remains for old tests and
    # any internal caller that still passes a label explicitly.
    if emp_id_row_label:
        id_label_norm = emp_id_row_label.strip().lower()
        id_row_index = None
        for idx, row in df.iterrows():
            cell = str(row.iloc[0]).strip().lower() if pd.notna(row.iloc[0]) else ""
            if cell == id_label_norm:
                id_row_index = idx
                break

        if id_row_index is None:
            result.errors.append(
                f"Employee number row not found. Expected a row in column A labelled "
                f"'{emp_id_row_label}'."
            )
            return result
    else:
        id_row_index = 0

    fixed_norms = {label.strip().lower() for label in fixed_info_row_labels}

    # 4. Identify employee columns (col B onwards)
    id_row = df.iloc[id_row_index]
    employee_columns: Dict[str, int] = {}

    for col_idx in range(1, len(df.columns)):
        raw_cell = id_row.iloc[col_idx]
        if pd.isna(raw_cell) or str(raw_cell).strip() == "":
            continue
        emp_number = _clean_employee_number(raw_cell)
        if not emp_number:
            result.warnings.append(
                f"Column {col_idx + 1}: empty employee number in ID row — skipped."
            )
            continue
        if emp_number in employee_columns:
            result.warnings.append(
                f"Employee number '{emp_number}' appears more than once. "
                f"Last column (column {col_idx + 1}) will be used."
            )
        employee_columns[emp_number] = col_idx

    if not employee_columns:
        result.errors.append("No employee numbers found in row 1.")
        return result

    # 5. Collect salary component rows
    component_rows: List[Tuple[int, str]] = []

    for idx, row in df.iterrows():
        if idx == id_row_index:
            continue
        raw_label = row.iloc[0]
        if pd.isna(raw_label) or str(raw_label).strip() == "":
            continue
        label = str(raw_label).strip()
        if label.lower() in fixed_norms:
            continue
        component_rows.append((idx, label))

    if not component_rows:
        result.warnings.append(
            "No salary component rows found after filtering. "
            "Check that fixed_info_row_labels is not too broad."
        )

    # 6. Parse each employee column
    for emp_number, col_idx in employee_columns.items():
        if emp_number not in known_employee_numbers:
            result.warnings.append(
                f"Employee number '{emp_number}' (column {col_idx + 1}) "
                f"not found in the system — skipped."
            )
            continue

        breakdown: Dict[str, Decimal] = {}
        for row_idx, label in component_rows:
            raw_value = df.iloc[row_idx, col_idx]
            amount = _parse_amount(raw_value, label, emp_number, result)
            breakdown[label] = amount

        gross_total = sum(breakdown.values(), Decimal("0"))
        result.records.append(EmployeeRecord(
            employee_number=emp_number,
            breakdown=breakdown,
            gross_total=gross_total,
        ))

    logger.info(
        "Parse complete: %d records, %d warnings, %d errors.",
        len(result.records), len(result.warnings), len(result.errors),
    )
    return result


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean_employee_number(raw) -> str:
    if pd.isna(raw):
        return ""
    s = str(raw).strip()
    # Excel float representation: "1.0" → "1"
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _parse_amount(raw, label: str, emp_number: str, result: ParseResult) -> Decimal:
    """Convert a cell value to Decimal. Handles all known edge cases."""
    if pd.isna(raw) or str(raw).strip() == "" or str(raw).strip().lower() == "nan":
        return Decimal("0")

    s = str(raw).strip()

    # Formula injection guard (= + @).
    # Does NOT include '-' because negative values are valid deductions.
    if s and s[0] in _INJECTION_PREFIXES:
        result.warnings.append(
            f"Employee '{emp_number}', row '{label}': "
            f"cell value '{s[:20]}' looks like a formula injection — treated as zero."
        )
        return Decimal("0")

    # Strip thousands separators
    s = s.replace(",", "")

    try:
        return Decimal(s)
    except InvalidOperation:
        result.warnings.append(
            f"Employee '{emp_number}', row '{label}': "
            f"could not parse '{raw}' as a number — treated as zero."
        )
        return Decimal("0")
