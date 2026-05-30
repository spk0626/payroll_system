"""
D5 tests: email notification service.
"""
from decimal import Decimal
from unittest.mock import patch, call
from django.test import TestCase
from django.utils import timezone

from employees.models import Branch, Employee, EmployeeCategory
from payroll.models import PaySheet, EmailLog
from payroll.services.email_service import send_payslip_notifications, retry_failed_emails
from core.constants import EmailStatus


def _make_emp(email, emp_no):
    branch = Branch.objects.get_or_create(name="HQ")[0]
    cat = EmployeeCategory.objects.get_or_create(name="Staff")[0]
    emp = Employee.objects.create(
        employee_number=emp_no, full_name="Test Person", email=email,
        date_of_joining="2024-01-01", bank_name="BOC",
        bank_account_name="Test", bank_branch_name="CMB",
        branch=branch, category=cat,
    )
    emp.refresh_from_db()
    return emp


def _make_paysheet(emp, month=1, year=2025):
    return PaySheet.objects.create(
        employee=emp, category_snapshot=emp.category,
        month=month, year=year,
        breakdown={"Basic": "50000"},
        gross_total=Decimal("50000"),
    )


# Patch the whole _send_one function to avoid SMTP + template rendering in unit tests.
# This is cleaner than patching EmailMultiAlternatives.send because it tests
# service-level behaviour (logging, error handling) not transport details.
_SEND_ONE = "payroll.services.email_service._send_one"


class TestSendPayslipNotifications(TestCase):
    def setUp(self):
        self.emp = _make_emp("notify@test.com", "EMP100")
        self.ps = _make_paysheet(self.emp)

    def test_successful_send_creates_sent_log(self):
        with patch(_SEND_ONE):
            result = send_payslip_notifications([self.ps])
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 0)
        log = EmailLog.objects.get(paysheet=self.ps)
        self.assertEqual(log.status, EmailStatus.SENT)

    def test_failed_send_logs_error_does_not_raise(self):
        with patch(_SEND_ONE, side_effect=Exception("SMTP connection refused")):
            result = send_payslip_notifications([self.ps])
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["failed"], 1)
        log = EmailLog.objects.get(paysheet=self.ps)
        self.assertEqual(log.status, EmailStatus.FAILED)
        self.assertIn("SMTP", log.error_message)

    def test_one_failure_does_not_abort_other_sends(self):
        emp2 = _make_emp("success@test.com", "EMP101")
        ps2 = _make_paysheet(emp2, month=2)
        call_count = {"n": 0}

        def side_effect(paysheet, employee):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("First fails")

        with patch(_SEND_ONE, side_effect=side_effect):
            result = send_payslip_notifications([self.ps, ps2])

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["total"], 2)

    def test_retry_only_sends_to_failed_recipients(self):
        emp2 = _make_emp("failed@test.com", "EMP102")
        ps_sent = _make_paysheet(self.emp, month=6)
        ps_failed = _make_paysheet(emp2, month=6)

        EmailLog.objects.create(
            paysheet=ps_sent, employee=self.emp,
            status=EmailStatus.SENT, batch_sent_at=timezone.now()
        )
        EmailLog.objects.create(
            paysheet=ps_failed, employee=emp2,
            status=EmailStatus.FAILED, batch_sent_at=timezone.now(),
            error_message="timeout"
        )

        with patch(_SEND_ONE) as mock_send_one:
            result = retry_failed_emails(month=6, year=2025)

        # Only emp2 (FAILED) should be retried
        self.assertEqual(result["total"], 1)
        self.assertEqual(mock_send_one.call_count, 1)


class TestEmailLogIdempotency(TestCase):
    def setUp(self):
        self.emp = _make_emp("idem@test.com", "EMP200")
        self.ps = _make_paysheet(self.emp, month=5)

    def test_duplicate_send_updates_existing_log_not_creates_new(self):
        with patch(_SEND_ONE):
            send_payslip_notifications([self.ps])
            send_payslip_notifications([self.ps])
        self.assertEqual(EmailLog.objects.filter(paysheet=self.ps).count(), 1)