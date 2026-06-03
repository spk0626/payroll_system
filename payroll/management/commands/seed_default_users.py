"""
Seed default admin and employee portal users.

This command is intentionally small and idempotent for deployment smoke tests.
Rotate these passwords after handover before storing real payroll data.
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from employees.models import Branch, Employee, EmployeeCategory


ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "SyntaxAdmin#2026!"

EMPLOYEE_NUMBER = "EMP001"
EMPLOYEE_EMAIL = "employee@example.com"
EMPLOYEE_PASSWORD = "SyntaxEmployee#2026!"


class Command(BaseCommand):
    help = "Create or reset default admin and employee portal users."

    def handle(self, *args, **options):
        admin_user, _ = User.objects.update_or_create(
            username=ADMIN_USERNAME,
            defaults={
                "email": ADMIN_EMAIL,
                "first_name": "System",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        admin_user.set_password(ADMIN_PASSWORD)
        admin_user.save()

        employee_user, _ = User.objects.update_or_create(
            username=EMPLOYEE_EMAIL,
            defaults={
                "email": EMPLOYEE_EMAIL,
                "first_name": "Demo",
                "last_name": "Employee",
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
            },
        )
        employee_user.set_password(EMPLOYEE_PASSWORD)
        employee_user.save()

        branch, _ = Branch.objects.get_or_create(
            name="Demo Branch",
            defaults={"location": "Colombo"},
        )
        category, _ = EmployeeCategory.objects.get_or_create(
            name="Demo Employees",
            defaults={"description": "Default employee category for deployment smoke tests."},
        )

        Employee.objects.update_or_create(
            employee_number=EMPLOYEE_NUMBER,
            defaults={
                "full_name": "Demo Employee",
                "email": EMPLOYEE_EMAIL,
                "date_of_joining": date(2026, 1, 1),
                "bank_name": "Demo Bank",
                "bank_account_name": "Demo Employee",
                "bank_branch_name": "Colombo",
                "branch": branch,
                "category": category,
                "user": employee_user,
                "is_active": True,
                "must_change_password": False,
            },
        )

        self.stdout.write(self.style.SUCCESS("Default users seeded."))
