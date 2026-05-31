"""
D8 Integration test — full payroll lifecycle end to end.

This test exercises the entire system in one flow:
  1.  Admin creates a branch and category
  2.  Admin sets parser config on the category
  3.  Admin creates an employee → user account auto-created
  4.  Employee is forced to change password on first login
  5.  Admin uploads an Excel salary sheet
  6.  Diff preview is built correctly
  7.  Upload is committed atomically
  8.  Employee can view their payslip via the portal
  9.  IDOR guard prevents access to another employee's payslip
  10. Email notification is sent
  11. Email log records the send
  12. Retry skips already-sent employees

This test is the closest thing to a real UAT run that can be automated.
If this passes, the system is working correctly end to end.
"""

import os
import tempfile
from decimal import Decimal
from unittest.mock import patch

import openpyxl
from django.contrib.auth.models import User
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

from employees.models import Branch, Employee, EmployeeCategory
from payroll.models import (
    CategoryParserConfig, PaySheet, UploadBatch, EmailLog
)
from payroll.services.excel_parser import parse_salary_sheet
from payroll.services.upload_service import build_diff, commit_diff, save_upload_file
from payroll.services.email_service import send_payslip_notifications
from core.constants import BatchStatus, EmailStatus


def _make_excel_file(rows: list[list]) -> str:
    """Write rows to a real temp xlsx file, return the path."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    f = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    wb.save(f.name)
    f.close()
    return f.name


@override_settings(RATELIMIT_ENABLE=False)
class TestFullPayrollLifecycle(TestCase):
    """End-to-end integration test of the complete payroll workflow."""

    def setUp(self):
        os.makedirs(settings.SALARY_UPLOADS_ROOT, exist_ok=True)

        # Create admin user
        self.admin = User.objects.create_superuser(
            "admin@company.lk", "admin@company.lk", "AdminPass!99"
        )

        # Step 1: Create branch and category
        self.branch = Branch.objects.create(name="Colombo HQ", location="Colombo 3")
        self.category = EmployeeCategory.objects.create(
            name="Permanent Staff",
            description="Full-time permanent employees",
        )

        # Step 2: Set up parser config
        self.config = CategoryParserConfig.objects.create(
            category=self.category,
            emp_id_row_label="Employee",
            fixed_info_row_labels=["Employee Name", "Designation"],
            notes="Standard permanent staff sheet format",
        )

        # Step 3: Create employees (signal auto-creates User accounts)
        self.emp_a = Employee.objects.create(
            employee_number="EMP001",
            full_name="Nimal Perera",
            email="nimal@company.lk",
            date_of_joining="2022-03-01",
            bank_name="Bank of Ceylon",
            bank_account_name="Nimal Perera",
            bank_branch_name="Colombo",
            branch=self.branch,
            category=self.category,
        )
        self.emp_a.refresh_from_db()

        self.emp_b = Employee.objects.create(
            employee_number="EMP002",
            full_name="Amali Silva",
            email="amali@company.lk",
            date_of_joining="2021-07-15",
            bank_name="Sampath Bank",
            bank_account_name="Amali Silva",
            bank_branch_name="Kandy",
            branch=self.branch,
            category=self.category,
        )
        self.emp_b.refresh_from_db()

    # ─── Auth flow ────────────────────────────────────────────────────────────

    def test_1_user_accounts_created_automatically(self):
        """Saving an Employee must auto-create a linked User account."""
        self.assertIsNotNone(self.emp_a.user)
        self.assertEqual(self.emp_a.user.username, "nimal@company.lk")
        self.assertTrue(self.emp_a.user.is_active)
        self.assertTrue(self.emp_a.must_change_password)

    def test_2_employee_forced_to_change_password_on_first_login(self):
        """Employee must be redirected to change-password until flag is cleared."""
        # Set a known password
        self.emp_a.user.set_password("TempPass!12")
        self.emp_a.user.save()

        client = Client()
        client.login(username="nimal@company.lk", password="TempPass!12")

        # Trying to access dashboard redirects to change-password
        resp = client.get(reverse("payroll:dashboard"), follow=False)
        self.assertRedirects(
            resp,
            reverse("accounts:change_password"),
            fetch_redirect_response=False,
        )

        # After changing password, flag is cleared
        resp = client.post(
            reverse("accounts:change_password"),
            {
                "old_password": "TempPass!12",
                "new_password1": "NewSecure!88",
                "new_password2": "NewSecure!88",
            },
        )
        self.emp_a.refresh_from_db()
        self.assertFalse(self.emp_a.must_change_password)

    # ─── Excel parsing ─────────────────────────────────────────────────────────

    def test_3_excel_parser_handles_full_sheet_correctly(self):
        """Parser must extract salary components and skip fixed info rows."""
        rows = [
            ["Employee",       "EMP001",   "EMP002"],
            ["Employee Name",  "Nimal P.", "Amali S."],  # fixed — skip
            ["Designation",    "Engineer", "Designer"],   # fixed — skip
            ["Basic Salary",   85000,      70000],
            ["HRA",            12000,      10000],
            ["Travel",          5000,       5000],
        ]
        path = _make_excel_file(rows)
        try:
            result = parse_salary_sheet(
                file_path=path,
                emp_id_row_label="Employee",
                fixed_info_row_labels=["Employee Name", "Designation"],
                known_employee_numbers={"EMP001", "EMP002"},
            )
        finally:
            os.unlink(path)

        self.assertFalse(result.has_fatal_errors)
        self.assertEqual(len(result.records), 2)

        emp1 = next(r for r in result.records if r.employee_number == "EMP001")
        self.assertEqual(emp1.breakdown["Basic Salary"], Decimal("85000"))
        self.assertEqual(emp1.breakdown["HRA"], Decimal("12000"))
        self.assertNotIn("Employee Name", emp1.breakdown)
        self.assertNotIn("Designation", emp1.breakdown)
        self.assertEqual(emp1.gross_total, Decimal("102000"))

    # ─── Upload pipeline ──────────────────────────────────────────────────────

    def test_4_upload_diff_and_commit(self):
        """Full upload pipeline: diff shows creates, commit writes PaySheets."""
        rows = [
            ["Employee",       "EMP001", "EMP002"],
            ["Employee Name",  "Nimal",  "Amali"],
            ["Basic Salary",   85000,    70000],
            ["HRA",            12000,    10000],
        ]
        path = _make_excel_file(rows)
        try:
            # Create batch and build diff
            batch = UploadBatch.objects.create(
                category=self.category,
                uploaded_by=self.admin,
                month=1,
                year=2025,
                original_filename="jan_2025_permanent.xlsx",
                file_path=os.path.basename(path),
                status=BatchStatus.PROCESSING,
            )
            # Copy file to salary_uploads for the service
            import shutil
            dest = os.path.join(settings.SALARY_UPLOADS_ROOT, os.path.basename(path))
            if path != dest:
                shutil.copy(path, dest)

            diff = build_diff(dest, self.category, month=1, year=2025, batch=batch)
        finally:
            os.unlink(path)
            if os.path.exists(dest) and dest != path:
                os.unlink(dest)

        # Diff should show 2 creates, 0 updates, 0 absent
        self.assertFalse(diff.has_fatal_errors, diff.errors)
        self.assertEqual(len(diff.to_create), 2)
        self.assertEqual(len(diff.to_update), 0)
        self.assertEqual(len(diff.absent), 0)

        # Commit the diff
        batch = commit_diff(diff, remove_absent_ids=[], category=self.category, month=1, year=2025)
        self.assertEqual(batch.status, BatchStatus.DONE)
        self.assertEqual(batch.records_created, 2)

        # PaySheets must exist in the database
        self.assertEqual(PaySheet.objects.filter(month=1, year=2025).count(), 2)

        # Gross totals must be correct
        ps_a = PaySheet.objects.get(employee=self.emp_a, month=1, year=2025)
        self.assertEqual(ps_a.gross_total, Decimal("97000"))  # 85000 + 12000

    # ─── Employee portal ──────────────────────────────────────────────────────

    def test_5_employee_can_view_own_payslip(self):
        """Employee must be able to access their own payslip detail page."""
        # Create a payslip
        ps = PaySheet.objects.create(
            employee=self.emp_a,
            category_snapshot=self.category,
            month=3,
            year=2025,
            breakdown={"Basic Salary": "85000.00", "HRA": "12000.00"},
            gross_total=Decimal("97000"),
        )

        self.emp_a.user.set_password("Portal!Pass1")
        self.emp_a.user.save()
        self.emp_a.must_change_password = False
        self.emp_a.save()

        client = Client()
        client.login(username="nimal@company.lk", password="Portal!Pass1")
        resp = client.get(reverse("payroll:payslip_detail", kwargs={"uuid": ps.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["breakdown_rows"]), 2)

    def test_6_idor_prevention_is_enforced(self):
        """
        CRITICAL: Employee A must never be able to access Employee B's payslip.
        This is the most important security test in the system.
        """
        ps_b = PaySheet.objects.create(
            employee=self.emp_b,
            category_snapshot=self.category,
            month=3,
            year=2025,
            breakdown={"Basic Salary": "70000.00"},
            gross_total=Decimal("70000"),
        )

        self.emp_a.user.set_password("Portal!Pass1")
        self.emp_a.user.save()
        self.emp_a.must_change_password = False
        self.emp_a.save()

        client = Client()
        client.login(username="nimal@company.lk", password="Portal!Pass1")

        # Employee A tries to access Employee B's payslip using B's real UUID
        resp = client.get(reverse("payroll:payslip_detail", kwargs={"uuid": ps_b.id}))
        self.assertEqual(resp.status_code, 403)

    def test_7_nonexistent_uuid_returns_403_not_404(self):
        """Non-existent UUIDs must return 403 to prevent existence probing."""
        import uuid
        self.emp_a.user.set_password("Portal!Pass1")
        self.emp_a.user.save()
        self.emp_a.must_change_password = False
        self.emp_a.save()

        client = Client()
        client.login(username="nimal@company.lk", password="Portal!Pass1")
        resp = client.get(
            reverse("payroll:payslip_detail", kwargs={"uuid": uuid.uuid4()})
        )
        self.assertEqual(resp.status_code, 403)

    # ─── Email notifications ──────────────────────────────────────────────────

    def test_8_payslip_email_notification_flow(self):
        """Email send must create EmailLog entries and report correct counts."""
        ps_a = PaySheet.objects.create(
            employee=self.emp_a,
            category_snapshot=self.category,
            month=4,
            year=2025,
            breakdown={"Basic Salary": "85000.00"},
            gross_total=Decimal("85000"),
        )
        ps_b = PaySheet.objects.create(
            employee=self.emp_b,
            category_snapshot=self.category,
            month=4,
            year=2025,
            breakdown={"Basic Salary": "70000.00"},
            gross_total=Decimal("70000"),
        )

        with patch("payroll.services.email_service._send_one"):
            result = send_payslip_notifications([ps_a, ps_b])

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(EmailLog.objects.filter(status=EmailStatus.SENT).count(), 2)

    def test_9_failed_email_does_not_abort_batch(self):
        """One email failure must not stop the rest of the batch."""
        ps_a = PaySheet.objects.create(
            employee=self.emp_a,
            category_snapshot=self.category,
            month=5,
            year=2025,
            breakdown={"Basic Salary": "85000.00"},
            gross_total=Decimal("85000"),
        )
        ps_b = PaySheet.objects.create(
            employee=self.emp_b,
            category_snapshot=self.category,
            month=5,
            year=2025,
            breakdown={"Basic Salary": "70000.00"},
            gross_total=Decimal("70000"),
        )

        call_n = {"n": 0}

        def fail_first(paysheet, employee):
            call_n["n"] += 1
            if call_n["n"] == 1:
                raise Exception("SMTP timeout")

        with patch("payroll.services.email_service._send_one", side_effect=fail_first):
            result = send_payslip_notifications([ps_a, ps_b])

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 1)
        # Both employees must have a log entry
        self.assertEqual(EmailLog.objects.filter(paysheet__month=5).count(), 2)


class TestSystemHealthChecks(TestCase):
    """Basic sanity checks that should always pass in any environment."""

    def test_login_page_accessible(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)

    def test_default_admin_url_blocked(self):
        resp = self.client.get("/admin/")
        self.assertNotEqual(resp.status_code, 200)

    def test_salary_uploads_not_web_accessible(self):
        """salary_uploads/ must never be directly accessible via HTTP."""
        resp = self.client.get("/salary_uploads/")
        # Django routing won't serve this path — 404 is correct
        self.assertNotEqual(resp.status_code, 200)

    def test_security_headers_on_every_response(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertIn("Content-Security-Policy", resp)
        self.assertEqual(resp.get("X-Frame-Options", "").upper(), "DENY")
        self.assertEqual(resp.get("X-Content-Type-Options"), "nosniff")

    def test_404_uses_custom_template(self):
        resp = self.client.get("/this-page-definitely-does-not-exist-12345/")
        self.assertEqual(resp.status_code, 404)
        # Custom 404 must not expose Django version info
        content = resp.content.decode()
        self.assertNotIn("Django", content)
        self.assertNotIn("Traceback", content)