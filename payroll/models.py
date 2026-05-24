"""
Payroll models: PaySheet, UploadBatch, EmailLog.

Design notes:
- PaySheet uses a UUID as its primary key. This is the public identifier
  used in all employee-facing URLs. Sequential integers would allow IDOR
  attacks (employee guessing other employees' payslip URLs by incrementing).
- breakdown is a JSONField storing {component_name: amount} for the month.
  Completely dynamic — no hardcoded salary components anywhere.
- category_snapshot is set at upload time and never changes, preserving
  historical accuracy even if the employee moves to a different category later.
- gross_total is computed at upload time and stored for fast rendering
  and future reporting. It is always the sum of all positive breakdown values.
- UploadBatch records every file upload with its processing log and warnings,
  giving admins a full audit trail of how salary data entered the system.
"""

import uuid

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import (
    GROSS_TOTAL_DECIMAL_PLACES,
    GROSS_TOTAL_MAX_DIGITS,
    MONTHS,
    BatchStatus,
    EmailStatus,
)
from employees.models import Employee, EmployeeCategory


class PaySheet(models.Model):
    """
    One employee's salary breakdown for one month.

    The UUID primary key is the public identifier used in employee-facing URLs.
    All views that render a payslip must also verify that the requesting user
    owns this PaySheet (paysheet.employee.user == request.user).
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name=_("ID"),
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,  # Cannot delete employee with paysheets
        related_name="paysheets",
        verbose_name=_("Employee"),
    )
    category_snapshot = models.ForeignKey(
        EmployeeCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name="paysheets",
        verbose_name=_("Category at time of upload"),
        help_text=_(
            "Records the employee's category when this paysheet was created. "
            "Unaffected by future category changes."
        ),
    )
    upload_batch = models.ForeignKey(
        "UploadBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paysheets",
        verbose_name=_("Upload batch"),
    )

    month = models.PositiveSmallIntegerField(
        choices=MONTHS,
        verbose_name=_("Month"),
    )
    year = models.PositiveSmallIntegerField(
        verbose_name=_("Year"),
    )

    breakdown = models.JSONField(
        default=dict,
        verbose_name=_("Salary breakdown"),
        help_text=_(
            'JSON object mapping component names to amounts. '
            'Example: {"Basic Salary": "50000.00", "HRA": "5000.00"}'
        ),
    )
    gross_total = models.DecimalField(
        max_digits=GROSS_TOTAL_MAX_DIGITS,
        decimal_places=GROSS_TOTAL_DECIMAL_PLACES,
        default=0,
        verbose_name=_("Gross total"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Pay sheet")
        verbose_name_plural = _("Pay sheets")
        # An employee can only have one paysheet per month
        unique_together = [("employee", "month", "year")]
        ordering = ["-year", "-month"]
        indexes = [
            models.Index(
                fields=["employee", "month", "year"],
                name="paysheet_emp_month_year_idx",
            ),
            models.Index(
                fields=["month", "year", "category_snapshot"],
                name="paysheet_month_year_cat_idx",
            ),
        ]

    def __str__(self) -> str:
        month_name = dict(MONTHS).get(self.month, str(self.month))
        return f"{self.employee.full_name} — {month_name} {self.year}"

    def get_month_display_name(self) -> str:
        return dict(MONTHS).get(self.month, str(self.month))


class UploadBatch(models.Model):
    """
    Records a single Excel file upload event.

    Every upload — successful or failed — creates an UploadBatch.
    This is the audit trail for how salary data entered the system.
    Admins can review warnings (unknown employee numbers) and processing logs.
    """

    category = models.ForeignKey(
        EmployeeCategory,
        on_delete=models.PROTECT,
        related_name="upload_batches",
        verbose_name=_("Target category"),
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="upload_batches",
        verbose_name=_("Uploaded by"),
    )

    month = models.PositiveSmallIntegerField(choices=MONTHS, verbose_name=_("Month"))
    year = models.PositiveSmallIntegerField(verbose_name=_("Year"))

    original_filename = models.CharField(
        max_length=255,
        verbose_name=_("Original filename"),
    )
    file_path = models.CharField(
        max_length=500,
        verbose_name=_("Stored file path"),
        help_text=_("Path relative to SALARY_UPLOADS_ROOT. Not web-accessible."),
    )

    status = models.CharField(
        max_length=20,
        choices=BatchStatus.CHOICES,
        default=BatchStatus.PENDING,
        verbose_name=_("Status"),
    )

    records_created = models.PositiveIntegerField(default=0, verbose_name=_("Records created"))
    records_updated = models.PositiveIntegerField(default=0, verbose_name=_("Records updated"))
    records_skipped = models.PositiveIntegerField(default=0, verbose_name=_("Records skipped"))

    warnings = models.JSONField(
        default=list,
        verbose_name=_("Warnings"),
        help_text=_("List of warning messages from the upload process."),
    )
    processing_log = models.TextField(
        blank=True,
        verbose_name=_("Processing log"),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Upload batch")
        verbose_name_plural = _("Upload batches")
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["month", "year", "category"],
                name="batch_month_year_cat_idx",
            ),
        ]

    def __str__(self) -> str:
        month_name = dict(MONTHS).get(self.month, str(self.month))
        return f"{self.category.name} — {month_name} {self.year} ({self.status})"


class EmailLog(models.Model):
    """
    Tracks every payslip email notification attempt.

    One record per employee per send batch.
    Enables per-employee retry without re-sending to successful recipients.
    """

    paysheet = models.ForeignKey(
        PaySheet,
        on_delete=models.CASCADE,
        related_name="email_logs",
        verbose_name=_("Pay sheet"),
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="email_logs",
        verbose_name=_("Employee"),
    )

    status = models.CharField(
        max_length=20,
        choices=EmailStatus.CHOICES,
        default=EmailStatus.PENDING,
        verbose_name=_("Status"),
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error message"),
        help_text=_("Populated if status is 'failed'."),
    )

    # When this specific email was attempted
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Sent at"))
    # The timestamp of the bulk send action that triggered this
    batch_sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Batch sent at"))

    class Meta:
        verbose_name = _("Email log")
        verbose_name_plural = _("Email logs")
        ordering = ["-batch_sent_at", "employee__full_name"]
        indexes = [
            models.Index(fields=["paysheet"], name="emaillog_paysheet_idx"),
            models.Index(fields=["status", "batch_sent_at"], name="emaillog_status_batch_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.employee.full_name} — {self.status}"
