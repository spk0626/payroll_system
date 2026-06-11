"""
Employee, Branch, and EmployeeCategory models.

Design notes:
- Employee is soft-deleted (is_active=False) — never hard deleted.
  Historical paysheets must survive an employee leaving the company.
- The OneToOne relationship to Django's User is the source of truth for login.
- must_change_password is set True on account creation (auto-generated password)
  and cleared when the employee successfully changes their password.
- category is nullable to handle the edge case of an employee whose category
  is deleted; but new employees always require a category.
"""

import logging

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.constants import (
    BANK_ACCOUNT_NAME_MAX_LENGTH,
    BANK_ACCOUNT_NUMBER_MAX_LENGTH,
    BANK_BRANCH_NAME_MAX_LENGTH,
    BANK_NAME_MAX_LENGTH,
    BRANCH_NAME_MAX_LENGTH,
    CATEGORY_NAME_MAX_LENGTH,
    EMPLOYEE_NAME_MAX_LENGTH,
    EMPLOYEE_NUMBER_MAX_LENGTH,
)

logger = logging.getLogger(__name__)


class Branch(models.Model):
    """
    A physical or logical branch of the company.

    Stored as a managed list so employee filters and reports are consistent.
    Free-text branch fields on Employee would lead to inconsistent data
    ("Colombo", "colombo", "CMB" all meaning the same thing).
    """

    name = models.CharField(
        max_length=BRANCH_NAME_MAX_LENGTH,
        unique=True,
        verbose_name=_("Branch name"),
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Location"),
        help_text=_("Optional: city, address, or region."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Branch")
        verbose_name_plural = _("Branches")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class EmployeeCategory(models.Model):
    """
    A payroll grouping for employees.

    Different categories can have completely different salary structures
    and different Excel upload formats. Each monthly Excel upload targets
    exactly one category.

    Examples: Permanent Staff, Contract Workers, Management, Sales.
    """

    name = models.CharField(
        max_length=CATEGORY_NAME_MAX_LENGTH,
        unique=True,
        verbose_name=_("Category name"),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Optional: describe what type of employees belong here."),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Employee category")
        verbose_name_plural = _("Employee categories")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Employee(models.Model):
    """
    Core employee record.

    Linked 1-to-1 with a Django User for authentication.
    The User account is created automatically via a post_save signal
    when a new Employee is saved (see employees/signals.py).

    The employee_number is the business identifier used in Excel uploads.
    It must match exactly (after stripping whitespace) for payroll processing.
    """

    # ── Identification ──────────────────────────────────────────────────────
    employee_number = models.CharField(
        max_length=EMPLOYEE_NUMBER_MAX_LENGTH,
        unique=True,
        db_index=True,
        verbose_name=_("Employee number"),
        help_text=_("Must match the employee number used in Excel payroll files."),
    )
    full_name = models.CharField(
        max_length=EMPLOYEE_NAME_MAX_LENGTH,
        verbose_name=_("Full name"),
    )
    email = models.EmailField(
        unique=True,
        verbose_name=_("Email address"),
        help_text=_("Used as the login username. Must be a working email address."),
    )
    date_of_joining = models.DateField(
        verbose_name=_("Date of joining"),
    )

    # ── Banking ─────────────────────────────────────────────────────────────
    bank_name = models.CharField(
        max_length=BANK_NAME_MAX_LENGTH,
        verbose_name=_("Bank name"),
    )
    bank_account_name = models.CharField(
        max_length=BANK_ACCOUNT_NAME_MAX_LENGTH,
        verbose_name=_("Bank account name"),
    )
    bank_account_number = models.CharField(
        max_length=BANK_ACCOUNT_NUMBER_MAX_LENGTH,
        blank=True,
        verbose_name=_("Bank account number"),
    )
    bank_branch_name = models.CharField(
        max_length=BANK_BRANCH_NAME_MAX_LENGTH,
        verbose_name=_("Bank branch name"),
    )

    # ── Organisation ────────────────────────────────────────────────────────
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,  # Can't delete a branch that has employees
        related_name="employees",
        verbose_name=_("Branch"),
    )
    category = models.ForeignKey(
        EmployeeCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Category"),
        help_text=_(
            "Determines which salary structure applies. "
            "Changing this does not affect historical paysheets."
        ),
    )

    # ── Account link ────────────────────────────────────────────────────────
    user = models.OneToOneField(
        User,
        on_delete=models.PROTECT,  # Deleting user must be deliberate, not cascade
        related_name="employee",
        verbose_name=_("User account"),
        null=True,
        blank=True,  # Null only transiently — signal sets this immediately after creation
    )

    # ── Status ──────────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=_(
            "Deactivate instead of deleting. Deactivated employees cannot log in "
            "but their payslip history is preserved."
        ),
    )
    must_change_password = models.BooleanField(
        default=True,
        verbose_name=_("Must change password"),
        help_text=_(
            "Set automatically when an account is created. Cleared when the "
            "employee successfully changes their initial password."
        ),
    )

    # ── Timestamps ──────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["is_active", "category"], name="emp_active_category_idx"),
            models.Index(fields=["branch"], name="emp_branch_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.employee_number})"

    def get_display_category(self) -> str:
        """Return category name or a clear fallback for display."""
        return self.category.name if self.category else "— No category assigned —"

    def deactivate(self) -> None:
        """
        Soft-delete: deactivate both the Employee and their User account.
        Never hard-deletes to preserve payslip history.
        """
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])
        if self.user:
            self.user.is_active = False
            self.user.save(update_fields=["is_active"])
        logger.info("Employee %s deactivated.", self.employee_number)
