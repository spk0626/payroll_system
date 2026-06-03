from django.contrib.auth.models import User
from django.core.management import call_command

from employees.models import Employee


def test_seed_default_users_is_idempotent(db):
    call_command("seed_default_users")
    call_command("seed_default_users")

    admin = User.objects.get(username="admin")
    assert admin.email == "admin@example.com"
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.check_password("SyntaxAdmin#2026!")

    employee_user = User.objects.get(username="employee@example.com")
    assert employee_user.email == "employee@example.com"
    assert employee_user.is_staff is False
    assert employee_user.is_superuser is False
    assert employee_user.check_password("SyntaxEmployee#2026!")

    employee = Employee.objects.get(employee_number="EMP001")
    assert employee.user == employee_user
    assert employee.email == "employee@example.com"
    assert employee.must_change_password is False
    assert Employee.objects.count() == 1
