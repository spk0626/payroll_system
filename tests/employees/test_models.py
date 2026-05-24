"""
Tests for employee models and signals.

Coverage:
- Branch and EmployeeCategory creation
- Employee creation triggers User account creation (signal)
- Generated password meets complexity requirements
- Employee deactivation soft-deletes both employee and user
- must_change_password is True on creation
- Employee number uniqueness enforced
"""

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from employees.models import Branch, Employee, EmployeeCategory
from employees.signals import _generate_secure_password


class TestPasswordGenerator(TestCase):
    def test_password_length(self):
        pwd = _generate_secure_password(length=14)
        assert len(pwd) == 14

    def test_password_complexity(self):
        for _ in range(50):  # Run multiple times to catch probabilistic failures
            pwd = _generate_secure_password()
            assert any(c.isupper() for c in pwd), "Missing uppercase"
            assert any(c.islower() for c in pwd), "Missing lowercase"
            assert any(c.isdigit() for c in pwd), "Missing digit"
            assert any(c in "!@#$%^&*" for c in pwd), "Missing special char"

    def test_passwords_are_unique(self):
        passwords = {_generate_secure_password() for _ in range(100)}
        assert len(passwords) == 100, "Duplicate passwords generated"


class TestBranch(TestCase):
    def test_create_branch(self):
        branch = Branch.objects.create(name="Colombo HQ", location="Colombo 3")
        assert str(branch) == "Colombo HQ"

    def test_branch_name_unique(self):
        Branch.objects.create(name="Unique Branch")
        with pytest.raises(IntegrityError):
            Branch.objects.create(name="Unique Branch")


class TestEmployeeCategory(TestCase):
    def test_create_category(self):
        cat = EmployeeCategory.objects.create(name="Permanent Staff")
        assert str(cat) == "Permanent Staff"

    def test_category_name_unique(self):
        EmployeeCategory.objects.create(name="Management")
        with pytest.raises(IntegrityError):
            EmployeeCategory.objects.create(name="Management")


class TestEmployeeSignal(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch")
        self.category = EmployeeCategory.objects.create(name="Test Category")

    def _make_employee(self, **kwargs):
        defaults = {
            "employee_number": "EMP001",
            "full_name": "Test User",
            "email": "test@example.com",
            "date_of_joining": "2024-01-01",
            "bank_name": "Bank of Ceylon",
            "bank_account_name": "Test User",
            "bank_branch_name": "Colombo",
            "branch": self.branch,
            "category": self.category,
        }
        defaults.update(kwargs)
        return Employee.objects.create(**defaults)

    def test_user_created_on_employee_creation(self):
        employee = self._make_employee()
        employee.refresh_from_db()
        assert employee.user is not None
        assert employee.user.username == "test@example.com"
        assert employee.user.email == "test@example.com"
        assert employee.user.is_active is True

    def test_must_change_password_is_true_on_creation(self):
        employee = self._make_employee()
        assert employee.must_change_password is True

    def test_user_not_duplicated_on_save(self):
        employee = self._make_employee()
        initial_user_id = employee.user_id
        employee.full_name = "Updated Name"
        employee.save()
        employee.refresh_from_db()
        assert employee.user_id == initial_user_id
        assert User.objects.filter(username="test@example.com").count() == 1

    def test_deactivate_soft_deletes_employee_and_user(self):
        employee = self._make_employee()
        employee.refresh_from_db()
        employee.deactivate()
        employee.refresh_from_db()
        assert employee.is_active is False
        assert employee.user.is_active is False

    def test_employee_number_must_be_unique(self):
        self._make_employee(employee_number="EMP001", email="first@example.com")
        with pytest.raises(IntegrityError):
            self._make_employee(employee_number="EMP001", email="second@example.com")

    def test_email_must_be_unique(self):
        self._make_employee(employee_number="EMP001", email="same@example.com")
        with pytest.raises(IntegrityError):
            self._make_employee(employee_number="EMP002", email="same@example.com")

    def test_str_representation(self):
        employee = self._make_employee()
        assert str(employee) == "Test User (EMP001)"
