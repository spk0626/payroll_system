"""
Admin configuration for the employees app.

Design goals:
- Every action is obvious — admins should never need to google "how to do X"
- Bulk category assignment is a dropdown action, one click
- Password reset is a bulk action with immediate email confirmation
- Payroll uploads read employee numbers from row 1, so categories stay simple
- Status badges make employee state instantly readable at a glance
"""

import logging
from datetime import date

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.admin_mixins import ActionLabelMixin
from .models import Branch, Employee, EmployeeCategory
from .signals import _generate_secure_password, sync_user_account

logger = logging.getLogger(__name__)


# ─── Branch ───────────────────────────────────────────────────────────────────

@admin.register(Branch)
class BranchAdmin(ActionLabelMixin, admin.ModelAdmin):
    list_display = ["name", "location", "employee_count", "created_at"]
    search_fields = ["name", "location"]
    ordering = ["name"]

    @admin.display(description="Active employees")
    def employee_count(self, obj: Branch) -> int:
        return obj.employees.filter(is_active=True).count()


# ─── EmployeeCategory (with inline parser config) ─────────────────────────────

@admin.register(EmployeeCategory)
class EmployeeCategoryAdmin(ActionLabelMixin, admin.ModelAdmin):
    list_display = [
        "name",
        "employee_count",
        "description_preview",
        "created_at",
    ]
    search_fields = ["name", "description"]
    ordering = ["name"]

    @admin.display(description="Active employees")
    def employee_count(self, obj: EmployeeCategory) -> int:
        return obj.employees.filter(is_active=True).count()

    @admin.display(description="Description")
    def description_preview(self, obj: EmployeeCategory) -> str:
        if not obj.description:
            return "—"
        return (obj.description[:80] + "…") if len(obj.description) > 80 else obj.description


# ─── Employee ─────────────────────────────────────────────────────────────────

def _assign_to_category_action_factory(category):
    """Dynamically create a bulk 'Assign to category' action per existing category."""

    def assign_action(modeladmin, request, queryset):
        updated = queryset.update(category=category)
        modeladmin.message_user(
            request,
            f"{updated} employee(s) assigned to '{category.name}'.",
            messages.SUCCESS,
        )

    assign_action.__name__ = f"assign_to_{category.pk}"
    assign_action.short_description = f"Assign selected to {category.name}"
    return assign_action


class EmployeeAdminForm(forms.ModelForm):
    date_of_joining_year = forms.ChoiceField(label="Joining year")
    date_of_joining_month = forms.ChoiceField(label="Joining month")

    class Meta:
        model = Employee
        fields = "__all__"
        widgets = {
            "date_of_joining": forms.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = date.today().year
        years = range(current_year, current_year - 16, -1)
        self.fields["date_of_joining_year"].choices = [(year, year) for year in years]
        self.fields["date_of_joining_month"].choices = [
            (1, "January"),
            (2, "February"),
            (3, "March"),
            (4, "April"),
            (5, "May"),
            (6, "June"),
            (7, "July"),
            (8, "August"),
            (9, "September"),
            (10, "October"),
            (11, "November"),
            (12, "December"),
        ]
        joining_date = self.instance.date_of_joining if self.instance.pk else date.today()
        self.fields["date_of_joining_year"].initial = joining_date.year
        self.fields["date_of_joining_month"].initial = joining_date.month

    def clean(self):
        cleaned_data = super().clean()
        year = cleaned_data.get("date_of_joining_year")
        month = cleaned_data.get("date_of_joining_month")
        if year and month:
            cleaned_data["date_of_joining"] = date(int(year), int(month), 1)
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data["email"]
        user_id = self.instance.user_id if self.instance and self.instance.pk else None
        duplicate_user = User.objects.filter(username=email).exclude(pk=user_id).exists()
        duplicate_email = User.objects.filter(email=email).exclude(pk=user_id).exists()
        if duplicate_user or duplicate_email:
            raise forms.ValidationError(
                "This email is already used by another login account."
            )
        return email


@admin.register(Employee)
class EmployeeAdmin(ActionLabelMixin, admin.ModelAdmin):
    # ── List view ─────────────────────────────────────────────────────────────
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
    date_hierarchy = "date_of_joining"
    form = EmployeeAdminForm

    # ── Detail view ────────────────────────────────────────────────────────────
    fieldsets = [
        (
            "Personal information",
            {
                "fields": [
                    "employee_number",
                    "full_name",
                    "email",
                    "date_of_joining_year",
                    "date_of_joining_month",
                ],
            },
        ),
        (
            "Organisation",
            {
                "fields": ["branch", "category", "is_active"],
                "description": (
                    "Changing category does not affect historical payslips — "
                    "they retain the category they were uploaded under."
                ),
            },
        ),
        (
            "Bank details",
            {
                "classes": ["collapse"],
                "fields": [
                    "bank_name",
                    "bank_account_number",
                    "bank_account_name",
                    "bank_branch_name",
                ],
                "description": "Shown on printed payslips. Expand to view or edit.",
            },
        ),
        (
            "Account",
            {
                "classes": ["collapse"],
                "fields": ["user", "must_change_password"],
                "description": (
                    "The user account is created automatically on employee creation. "
                    "Use the Reset passwords action from the list view to generate a new password."
                ),
            },
        ),
    ]
    readonly_fields = ["user"]

    def response_add(self, request, obj, post_url_continue=None):
        password = getattr(obj, "_generated_password", None)
        if password:
            self.message_user(
                request,
                (
                    f"Temporary password for {obj.email}: {password} "
                    "This is shown once. It has also been emailed to the employee."
                ),
                messages.WARNING,
            )
        return super().response_add(request, obj, post_url_continue)

    # ── Actions ───────────────────────────────────────────────────────────────
    actions = ["reset_passwords", "deactivate_employees", "activate_employees"]

    def get_actions(self, request):
        """Add one 'Assign to category' action per existing category."""
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
        """Generate a new password, email it, set must_change_password=True."""
        count = 0
        for employee in queryset.select_related("user"):
            if not employee.user:
                continue
            if not sync_user_account(employee):
                self.message_user(
                    request,
                    f"Could not sync login email for {employee.employee_number}. "
                    "Check for duplicate user emails before resetting the password.",
                    messages.ERROR,
                )
                continue
            new_password = _generate_secure_password()
            employee.user.set_password(new_password)
            employee.user.save(update_fields=["password"])
            employee.must_change_password = True
            employee.save(update_fields=["must_change_password", "updated_at"])
            from .signals import _send_welcome_email
            _send_welcome_email(employee, new_password)
            count += 1
            logger.info(
                "Password reset by %s for employee %s.",
                request.user.username,
                employee.employee_number,
            )

        self.message_user(
            request,
            f"✓ Passwords reset for {count} employee(s). "
            "New passwords have been emailed to them.",
            messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected employees")
    def deactivate_employees(self, request, queryset):
        count = sum(1 for emp in queryset if emp.is_active and (emp.deactivate() or True))
        self.message_user(
            request,
            f"{count} employee(s) deactivated. Payslip history preserved.",
            messages.SUCCESS,
        )

    @admin.action(description="Re-activate selected employees")
    def activate_employees(self, request, queryset):
        updated = queryset.update(is_active=True)
        user_ids = queryset.values_list("user_id", flat=True)
        User.objects.filter(pk__in=user_ids).update(is_active=True)
        self.message_user(request, f"{updated} employee(s) re-activated.", messages.SUCCESS)

    # ── Display helpers ───────────────────────────────────────────────────────

    @admin.display(description="Status", ordering="is_active")
    def status_badge(self, obj: Employee):
        if obj.is_active:
            return format_html(
                '<span style="color:#2e7d32;font-weight:600;">● Active</span>'
            )
        return format_html(
            '<span style="color:#c62828;font-weight:600;">● Inactive</span>'
        )

    @admin.display(description="Login")
    def account_status(self, obj: Employee):
        if not obj.user:
            return format_html('<span style="color:#b45309;font-size:12px;">No account</span>')
        if obj.must_change_password:
            return format_html(
                '<span style="color:#b45309;font-size:12px;">Password change required</span>'
            )
        return format_html('<span style="color:#2e7d32;font-size:12px;">Active</span>')
