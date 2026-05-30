"""
Upload service: orchestrates the Excel upload pipeline.

Responsibilities:
  1. Save the uploaded file to SALARY_UPLOADS_ROOT with a randomised name
  2. Create an UploadBatch record
  3. Call the parser and get a ParseResult
  4. Build a DiffResult (what will be created, updated, absent)
  5. Commit the diff atomically on admin confirmation

This module contains NO views, NO HTTP. It is called by views in payroll/views.py.
Keeping business logic here makes it independently testable.
"""

import logging
import os
import secrets
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from employees.models import Employee
from payroll.models import CategoryParserConfig, PaySheet, UploadBatch
from payroll.services.excel_parser import ParseResult, parse_salary_sheet
from core.constants import BatchStatus

logger = logging.getLogger(__name__)


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class DiffEntry:
    """One employee's position in the diff between file and database."""
    employee: Employee
    action: str               # "create" | "update" | "absent"
    breakdown: Optional[dict] = None
    gross_total: Optional[Decimal] = None
    existing_paysheet: Optional[PaySheet] = None


@dataclass
class DiffResult:
    """
    The full diff between an uploaded file and the current database state.

    Presented to the admin before they confirm the upload commit.
    """
    to_create: list[DiffEntry] = field(default_factory=list)
    to_update: list[DiffEntry] = field(default_factory=list)
    absent: list[DiffEntry] = field(default_factory=list)   # in DB but not in file
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    batch_id: Optional[int] = None

    @property
    def has_changes(self) -> bool:
        return bool(self.to_create or self.to_update)

    @property
    def has_fatal_errors(self) -> bool:
        return bool(self.errors)


# ─── Step 1: Save file ────────────────────────────────────────────────────────

def save_upload_file(uploaded_file, category, month: int, year: int, user) -> tuple[str, UploadBatch]:
    """
    Save the uploaded file to private storage and create an UploadBatch record.

    Returns (absolute_file_path, batch).
    The file is stored with a random name to prevent enumeration.
    """
    upload_dir = settings.SALARY_UPLOADS_ROOT
    os.makedirs(upload_dir, exist_ok=True)

    _, ext = os.path.splitext(uploaded_file.name)
    safe_name = f"{secrets.token_hex(16)}{ext}"
    abs_path = os.path.join(upload_dir, safe_name)

    with open(abs_path, "wb") as dst:
        for chunk in uploaded_file.chunks():
            dst.write(chunk)

    batch = UploadBatch.objects.create(
        category=category,
        uploaded_by=user,
        month=month,
        year=year,
        original_filename=uploaded_file.name,
        file_path=safe_name,
        status=BatchStatus.PROCESSING,
    )

    logger.info(
        "Saved upload for category '%s' %s/%s as '%s' (batch %s).",
        category.name, month, year, safe_name, batch.pk,
    )
    return abs_path, batch


# ─── Step 2: Parse and build diff ─────────────────────────────────────────────

def build_diff(abs_path: str, category, month: int, year: int, batch: UploadBatch) -> DiffResult:
    """
    Parse the Excel file and compare against the current database state.

    Returns a DiffResult that the view can present to the admin for confirmation.
    Does not write any PaySheet records.
    """
    result = DiffResult(batch_id=batch.pk)

    # Load parser config for this category
    try:
        config = category.parser_config
    except CategoryParserConfig.DoesNotExist:
        result.errors.append(
            f"No parser configuration found for category '{category.name}'. "
            f"Please set up the parser configuration before uploading."
        )
        _mark_batch_failed(batch, result)
        return result

    # Get all known employee numbers for this category (used by parser for quick lookup)
    known_numbers = set(
        Employee.objects.filter(category=category, is_active=True)
        .values_list("employee_number", flat=True)
    )

    # Parse the file
    parse_result: ParseResult = parse_salary_sheet(
        file_path=abs_path,
        emp_id_row_label=config.emp_id_row_label,
        fixed_info_row_labels=config.fixed_info_row_labels or [],
        known_employee_numbers=known_numbers,
    )

    result.warnings.extend(parse_result.warnings)
    if parse_result.has_fatal_errors:
        result.errors.extend(parse_result.errors)
        _mark_batch_failed(batch, result)
        return result

    # Map employee_number → Employee object for records that passed parsing
    parsed_numbers = {r.employee_number for r in parse_result.records}
    employees_map: dict[str, Employee] = {
        emp.employee_number: emp
        for emp in Employee.objects.filter(
            employee_number__in=parsed_numbers, is_active=True
        ).select_related("category", "user")
    }

    # Existing paysheets for this month/category
    existing_paysheets: dict[int, PaySheet] = {
        ps.employee_id: ps
        for ps in PaySheet.objects.filter(
            month=month, year=year, category_snapshot=category
        ).select_related("employee")
    }

    # Build diff
    parsed_employee_ids: set[int] = set()

    for record in parse_result.records:
        emp = employees_map.get(record.employee_number)
        if emp is None:
            result.warnings.append(
                f"Employee '{record.employee_number}' not found after parse — skipped."
            )
            continue

        parsed_employee_ids.add(emp.pk)
        breakdown_serialisable = {k: str(v) for k, v in record.breakdown.items()}

        if emp.pk in existing_paysheets:
            result.to_update.append(DiffEntry(
                employee=emp,
                action="update",
                breakdown=breakdown_serialisable,
                gross_total=record.gross_total,
                existing_paysheet=existing_paysheets[emp.pk],
            ))
        else:
            result.to_create.append(DiffEntry(
                employee=emp,
                action="create",
                breakdown=breakdown_serialisable,
                gross_total=record.gross_total,
            ))

    # Employees in DB for this month but NOT in this file
    for emp_id, ps in existing_paysheets.items():
        if emp_id not in parsed_employee_ids:
            result.absent.append(DiffEntry(
                employee=ps.employee,
                action="absent",
                existing_paysheet=ps,
            ))

    return result


# ─── Step 3: Commit ───────────────────────────────────────────────────────────

def commit_diff(
    diff: DiffResult,
    remove_absent_ids: list[int],
    category,
    month: int,
    year: int,
) -> UploadBatch:
    """
    Atomically apply the diff to the database.

    Args:
        diff:              The DiffResult from build_diff().
        remove_absent_ids: List of Employee PKs from absent[] that admin chose to remove.
        category:          The EmployeeCategory being processed.
        month / year:      The payroll period.

    All writes happen inside a single transaction. If anything fails,
    the entire batch is rolled back and the database is unchanged.
    """
    batch = UploadBatch.objects.get(pk=diff.batch_id)

    try:
        with transaction.atomic():
            created = 0
            updated = 0

            for entry in diff.to_create:
                PaySheet.objects.create(
                    employee=entry.employee,
                    category_snapshot=category,
                    upload_batch=batch,
                    month=month,
                    year=year,
                    breakdown=entry.breakdown,
                    gross_total=entry.gross_total,
                )
                created += 1

            for entry in diff.to_update:
                ps = entry.existing_paysheet
                ps.breakdown = entry.breakdown
                ps.gross_total = entry.gross_total
                ps.upload_batch = batch
                ps.save(update_fields=["breakdown", "gross_total", "upload_batch", "updated_at"])
                updated += 1

            # Remove absent records the admin explicitly chose to remove
            if remove_absent_ids:
                PaySheet.objects.filter(
                    employee_id__in=remove_absent_ids,
                    month=month,
                    year=year,
                    category_snapshot=category,
                ).delete()

        batch.status = BatchStatus.DONE
        batch.records_created = created
        batch.records_updated = updated
        batch.records_skipped = len(diff.warnings)
        batch.warnings = diff.warnings
        batch.processing_log = _build_log(diff, remove_absent_ids)
        batch.save()

        logger.info(
            "Batch %s committed: %d created, %d updated, %d removed.",
            batch.pk, created, updated, len(remove_absent_ids),
        )

    except Exception as exc:
        batch.status = BatchStatus.FAILED
        batch.processing_log = f"Commit failed: {exc}"
        batch.save(update_fields=["status", "processing_log"])
        logger.exception("Batch %s commit failed.", batch.pk)
        raise

    return batch


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mark_batch_failed(batch: UploadBatch, result: DiffResult) -> None:
    batch.status = BatchStatus.FAILED
    batch.warnings = result.warnings
    batch.processing_log = "\n".join(result.errors)
    batch.save(update_fields=["status", "warnings", "processing_log"])


def _build_log(diff: DiffResult, remove_absent_ids: list[int]) -> str:
    lines = [
        f"Created: {len(diff.to_create)}",
        f"Updated: {len(diff.to_update)}",
        f"Removed: {len(remove_absent_ids)}",
        f"Absent kept: {len(diff.absent) - len(remove_absent_ids)}",
        f"Warnings: {len(diff.warnings)}",
    ]
    if diff.warnings:
        lines.append("\nWarnings:")
        lines.extend(f"  - {w}" for w in diff.warnings)
    return "\n".join(lines)