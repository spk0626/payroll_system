"""
D6 tests: admin panel actions and management command.
"""

import os
import tempfile
from io import BytesIO
from decimal import Decimal
from unittest.mock import patch

import openpyxl
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

from employees.models import Branch, Employee, EmployeeCategory
from payroll.models import (
    CategoryParserConfig, PaySheet, UploadBatch, EmailLog
)
from core.constants import BatchStatus, EmailStatus


def _make_emp(email, emp_no):
    branch = Branch.objects.get_or_create(name="HQ")[0]
    cat = EmployeeCategory.objects.get_or_create(name="Staff")[0]
    emp = Employee.objects.create(
        employee_number=emp_no, full_name="Test", email=email,
        date_of_joining="2024-01-01", bank_name="BOC",
        bank_account_name="Test", bank_branch_name="CMB",
        branch=branch, category=cat,
    )
    emp.refresh_from_db()
    return emp


def _make_batch(category, month=1, year=2025, status=BatchStatus.DONE):
    return UploadBatch.objects.create(
        category=category,
        month=month,
        year=year,
        original_filename="test.xlsx",
        file_path="test_file.xlsx",
        status=status,
    )


def _make_paysheet(emp, batch=None, month=1, year=2025):
    return PaySheet.objects.create(
        employee=emp,
        category_snapshot=emp.category,
        upload_batch=batch,
        month=month,
        year=year,
        breakdown={"Basic": "50000"},
        gross_total=Decimal("50000"),
    )


class TestCategoryParserConfigAdmin(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            "admin@test.com", "admin@test.com", "Admin!Pass123"
        )
        self.client.login(username="admin@test.com", password="Admin!Pass123")
        self.cat = EmployeeCategory.objects.create(name="Test Category")

    def test_can_view_category_list(self):
        resp = self.client.get(
            f"/{settings.ADMIN_URL}employees/employeecategory/"
        )
        self.assertEqual(resp.status_code, 200)

    def test_parser_config_inline_on_category_page(self):
        resp = self.client.get(
            f"/{settings.ADMIN_URL}employees/employeecategory/{self.cat.pk}/change/"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Excel parser configuration")


class TestUploadBatchAdminActions(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            "admin@test.com", "admin@test.com", "Admin!Pass123"
        )
        self.client.login(username="admin@test.com", password="Admin!Pass123")
        self.emp = _make_emp("emp@test.com", "EMP300")
        self.batch = _make_batch(self.emp.category)
        self.ps = _make_paysheet(self.emp, batch=self.batch)

    def test_batch_list_renders(self):
        resp = self.client.get(
            f"/{settings.ADMIN_URL}payroll/uploadbatch/"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Upload salary sheet")

    def test_upload_salary_sheet_admin_view_processes_file(self):
        CategoryParserConfig.objects.create(
            category=self.emp.category,
            emp_id_row_label="Employee",
            fixed_info_row_labels=[],
        )
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Employee", self.emp.employee_number])
        ws.append(["Basic", 50000])
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        upload = SimpleUploadedFile(
            "salary.xlsx",
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        resp = self.client.post(
            f"/{settings.ADMIN_URL}payroll/uploadbatch/upload-salary-sheet/",
            {
                "category": self.emp.category.pk,
                "month": 2,
                "year": 2025,
                "salary_file": upload,
            },
            follow=True,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            PaySheet.objects.filter(employee=self.emp, month=2, year=2025).exists()
        )

    def test_upload_requires_parser_config_before_saving_batch(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Employee", self.emp.employee_number])
        ws.append(["Basic", 50000])
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        upload = SimpleUploadedFile(
            "salary.xlsx",
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        resp = self.client.post(
            f"/{settings.ADMIN_URL}payroll/uploadbatch/upload-salary-sheet/",
            {
                "category": self.emp.category.pk,
                "month": 2,
                "year": 2025,
                "salary_file": upload,
            },
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "does not have an Excel parser configuration")
        self.assertEqual(UploadBatch.objects.count(), 1)

    def test_send_email_action(self):
        with patch("payroll.services.email_service._send_one"):
            resp = self.client.post(
                f"/{settings.ADMIN_URL}payroll/uploadbatch/",
                {
                    "action": "send_payslip_emails",
                    "_selected_action": [self.batch.pk],
                },
                follow=True,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(EmailLog.objects.filter(paysheet=self.ps).count(), 1)

    def test_retry_email_action_only_retries_failed(self):
        EmailLog.objects.create(
            paysheet=self.ps, employee=self.emp,
            status=EmailStatus.FAILED, batch_sent_at=timezone.now(),
            error_message="timeout"
        )
        with patch("payroll.services.email_service._send_one") as mock_send:
            self.client.post(
                f"/{settings.ADMIN_URL}payroll/uploadbatch/",
                {
                    "action": "retry_failed_emails_action",
                    "_selected_action": [self.batch.pk],
                },
                follow=True,
            )
        self.assertEqual(mock_send.call_count, 1)

    def test_retry_email_action_is_scoped_to_selected_batch(self):
        other_emp = _make_emp("other@test.com", "EMP302")
        other_batch = _make_batch(other_emp.category, month=self.batch.month, year=self.batch.year)
        other_ps = _make_paysheet(other_emp, batch=other_batch)
        EmailLog.objects.create(
            paysheet=self.ps, employee=self.emp,
            status=EmailStatus.FAILED, batch_sent_at=timezone.now(),
            error_message="timeout"
        )
        EmailLog.objects.create(
            paysheet=other_ps, employee=other_emp,
            status=EmailStatus.FAILED, batch_sent_at=timezone.now(),
            error_message="timeout"
        )

        with patch("payroll.services.email_service._send_one") as mock_send:
            self.client.post(
                f"/{settings.ADMIN_URL}payroll/uploadbatch/",
                {
                    "action": "retry_failed_emails_action",
                    "_selected_action": [self.batch.pk],
                },
                follow=True,
            )

        self.assertEqual(mock_send.call_count, 1)
        other_log = EmailLog.objects.get(paysheet=other_ps)
        self.assertEqual(other_log.status, EmailStatus.FAILED)


class TestPaySheetAdmin(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            "admin@test.com", "admin@test.com", "Admin!Pass123"
        )
        self.client.login(username="admin@test.com", password="Admin!Pass123")
        self.emp = _make_emp("paysheet-admin@test.com", "EMP303")
        self.ps = _make_paysheet(self.emp)

    def test_change_page_renders(self):
        resp = self.client.get(
            f"/{settings.ADMIN_URL}payroll/paysheet/{self.ps.pk}/change/"
        )

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Salary data")


class TestEmailLogRetryAction(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            "admin@test.com", "admin@test.com", "Admin!Pass123"
        )
        self.client.login(username="admin@test.com", password="Admin!Pass123")
        self.emp = _make_emp("emp2@test.com", "EMP301")
        self.ps = _make_paysheet(self.emp, month=7)

    def test_retry_action_on_email_log(self):
        log = EmailLog.objects.create(
            paysheet=self.ps, employee=self.emp,
            status=EmailStatus.FAILED, batch_sent_at=timezone.now(),
            error_message="SMTP error"
        )
        with patch("payroll.services.email_service._send_one"):
            resp = self.client.post(
                f"/{settings.ADMIN_URL}payroll/emaillog/",
                {
                    "action": "retry_selected_emails",
                    "_selected_action": [log.pk],
                },
                follow=True,
            )
        self.assertEqual(resp.status_code, 200)
        log.refresh_from_db()
        self.assertEqual(log.status, EmailStatus.SENT)


class TestPurgeOldUploadsCommand(TestCase):
    def setUp(self):
        self.cat = EmployeeCategory.objects.get_or_create(name="Staff")[0]

    def test_dry_run_does_not_delete_files(self):
        # Create a real temp file and an old batch pointing to it
        os.makedirs(settings.SALARY_UPLOADS_ROOT, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            dir=settings.SALARY_UPLOADS_ROOT,
            delete=False
        ) as f:
            fname = os.path.basename(f.name)

        from django.utils import timezone
        from datetime import timedelta

        batch = UploadBatch.objects.create(
            category=self.cat,
            month=1, year=2020,
            original_filename="old.xlsx",
            file_path=fname,
            status=BatchStatus.DONE,
        )
        # Backdate the batch
        UploadBatch.objects.filter(pk=batch.pk).update(
            created_at=timezone.now() - timedelta(days=400)
        )

        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command("purge_old_uploads", "--dry-run", stdout=out)

        # File should still exist
        abs_path = os.path.join(settings.SALARY_UPLOADS_ROOT, fname)
        self.assertTrue(os.path.exists(abs_path))
        os.unlink(abs_path)  # cleanup
        self.assertIn("Would delete", out.getvalue())

    def test_real_run_deletes_old_files(self):
        os.makedirs(settings.SALARY_UPLOADS_ROOT, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            dir=settings.SALARY_UPLOADS_ROOT,
            delete=False
        ) as f:
            fname = os.path.basename(f.name)

        from django.utils import timezone
        from datetime import timedelta

        batch = UploadBatch.objects.create(
            category=self.cat,
            month=1, year=2020,
            original_filename="old.xlsx",
            file_path=fname,
            status=BatchStatus.DONE,
        )
        UploadBatch.objects.filter(pk=batch.pk).update(
            created_at=timezone.now() - timedelta(days=400)
        )

        from django.core.management import call_command
        call_command("purge_old_uploads", "--months", "6")

        abs_path = os.path.join(settings.SALARY_UPLOADS_ROOT, fname)
        self.assertFalse(os.path.exists(abs_path))
        # DB record should still exist
        self.assertTrue(UploadBatch.objects.filter(pk=batch.pk).exists())
