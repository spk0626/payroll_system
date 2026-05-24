"""
Admin configuration for the employees app.

Design goals:
- Every action should be obvious — admins should never need to google "how to do X"
- Bulk actions are prominent and clearly labelled
- Password reset is a single click with immediate feedback
- Filters cover the most common admin workflows
"""

import logging

from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Branch, Employee, EmployeeCategory
from .signals import _generate_secure_password

logger = logging.getLogger(__name__)


# ─── Branch ───────────────────────────────────────────────────────────────────

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    """
    Simple admin for branch management.
    Branches are referenced by employees, so they cannot be deleted
    while employees are assigned (enforced by PROTECT on the FK).
    """

    list_display = ["name", "location", "employee_count", "created_at"]
    search_fields = ["name", "location"]
    ordering = ["name"]

    @admin.display(description="Employees")
    def employee_count(self, obj: Branch) -> int:
        return obj.employees.filter(is_active=True).count()


# ─── EmployeeCategory ─────────────────────────────────────────────────────────

@admin.register(EmployeeCategory)
class EmployeeCategoryAdmin(admin.ModelAdmin):
    """
    Admin for employee categories.

    Categories are the primary grouping for payroll uploads. Each monthly
    Excel file targets one category. Admins need to see at a glance how many
    employees are in each category and what their names are.
    """

    list_display = ["name", "employee_count", "description_preview", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["name"]

    @admin.display(description="Employees")
    def employee_count(self, obj: EmployeeCategory) -> int:
        return obj.employees.filter(is_active=True).count()

    @admin.display(description="Description")
    def description_preview(self, obj: EmployeeCategory) -> str:
        if not obj.description:
            return "—"
        return obj.description[:80] + ("…" if len(obj.description) > 80 else "")


# ─── Employee ─────────────────────────────────────────────────────────────────

def _assign_to_category_action_factory(category):
    """
    Dynamically create a bulk action for assigning employees to a specific category.

    Django admin bulk actions need to be defined per category, so we generate
    them at registration time. This factory creates one action per category.
    """

    def assign_action(modeladmin, request, queryset):
        updated = queryset.update(category=category)
        modeladmin.message_user(
            request,
            f"{updated} employee(s) assigned to '{category.name}'.",
            messages.SUCCESS,
        )

    assign_action.__name__ = f"assign_to_{category.pk}"
    assign_action.short_description = f"Assign selected to: {category.name}"
    return assign_action


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Main employee management interface.

    Key design decisions:
    - is_active filter is prominent (most common workflow: find active employees)
    - Password reset is a button in the detail view, not buried in a submenu
    - Category assignment is a bulk action available from the list view
    - Bank details are in a collapsed fieldset (sensitive; not needed most times)
    - The employee's login email is shown alongside their name
    """

    # ── List view ─────────────────────────────────────────────────────────
    list_display = [
        "employee_number",
        "full_name",
        "email",
        "branch",
        "category",
        "date_of_joining",
        "status_badge",
        "account_status",
    ]
    list_display_links = ["employee_number", "full_name"]
    list_filter = ["is_active", "branch", "category", "date_of_joining"]
    search_fields = ["employee_number", "full_name", "email"]
    ordering = ["full_name"]
    list_per_page = 50
    list_select_related = ["branch", "category", "user"]

    # ── Detail view ────────────────────────────────────────────────────────
    fieldsets = [
        (
            "Personal information",
            {
                "fields": [
                    "employee_number",
                    "full_name",
                    "email",
                    "date_of_joining",
                ],
            },
        ),
        (
            "Organisation",
            {
                "fields": ["branch", "category", "is_active"],
            },
        ),
        (
            "Bank details",
            {
                "classes": ["collapse"],  # Collapsed by default — sensitive data
                "fields": ["bank_name", "bank_account_name", "bank_branch_name"],
                "description": "These details are shown on payslips.",
            },
        ),
        (
            "Account",
            {
                "classes": ["collapse"],
                "fields": ["user", "must_change_password"],
                "description": (
                    "The User account is created automatically. "
                    "Use the 'Reset password' action to generate a new password."
                ),
            },
        ),
    ]
    readonly_fields = ["user"]

    # ── Actions ───────────────────────────────────────────────────────────
    actions = ["reset_passwords", "deactivate_employees", "activate_employees"]

    def get_actions(self, request):
        """
        Dynamically add one 'Assign to category' action per existing category.
        This makes bulk assignment available without navigating to each employee.
        """
        actions = super().get_actions(request)
        for category in EmployeeCategory.objects.all():
            action = _assign_to_category_action_factory(category)
            actions[action.__name__] = (
                action,
                action.__name__,
                action.short_description,
            )
        return actions

    @admin.action(description="Reset passwords for selected employees")
    def reset_passwords(self, request, queryset):
        """
        Generate a new random password for each selected employee.
        The new password is emailed to the employee and shown in the admin message.
        Sets must_change_password=True so they are prompted to change it on login.
        """
        results = []
        for employee in queryset.select_related("user"):
            if not employee.user:
                results.append(f"{employee.full_name}: no user account found")
                continue
            new_password = _generate_secure_password()
            employee.user.set_password(new_password)
            employee.user.save(update_fields=["password"])
            employee.must_change_password = True
            employee.save(update_fields=["must_change_password", "updated_at"])
            results.append(f"{employee.full_name} ({employee.email}): reset")
            logger.info(
                "Password reset by admin %s for employee %s.",
                request.user.username,
                employee.employee_number,
            )
            # Re-send welcome email with new password
            from .signals import _send_welcome_email
            _send_welcome_email(employee, new_password)

        self.message_user(
            request,
            f"Passwords reset for {len(results)} employee(s). "
            "New passwords have been emailed to them.",
            messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected employees (preserve payslip history)")
    def deactivate_employees(self, request, queryset):
        count = 0
        for employee in queryset:
            if employee.is_active:
                employee.deactivate()
                count += 1
        self.message_user(
            request,
            f"{count} employee(s) deactivated. Their payslip history is preserved.",
            messages.SUCCESS,
        )

    @admin.action(description="Re-activate selected employees")
    def activate_employees(self, request, queryset):
        updated = queryset.update(is_active=True)
        # Also re-activate their user accounts
        user_ids = queryset.values_list("user_id", flat=True)
        User.objects.filter(pk__in=user_ids).update(is_active=True)
        self.message_user(
            request,
            f"{updated} employee(s) re-activated.",
            messages.SUCCESS,
        )

    # ── Display helpers ───────────────────────────────────────────────────

    @admin.display(description="Status", ordering="is_active")
    def status_badge(self, obj: Employee):
        if obj.is_active:
            return format_html('<span style="color:#2e7d32;font-weight:500;">● Active</span>')
        return format_html('<span style="color:#c62828;font-weight:500;">● Inactive</span>')

    @admin.display(description="Login account")
    def account_status(self, obj: Employee):
        if not obj.user:
            return format_html('<span style="color:#e65100;">⚠ No account</span>')
        if obj.must_change_password:
            return format_html('<span style="color:#f57f17;">⚠ Password not changed</span>')
        return format_html('<span style="color:#2e7d32;">✓ Active</span>')
