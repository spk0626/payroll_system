"""
D3 tests: employee portal views and IDOR prevention.

Critical test: employee A cannot access employee B's payslip UUID even
if they somehow obtain it. This is the most important security test in
the entire system.
"""
import uuid
from decimal import Decimal
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from employees.models import Branch, Employee, EmployeeCategory
from payroll.models import PaySheet


def _make_employee(email, emp_no):
    branch = Branch.objects.get_or_create(name="HQ")[0]
    cat = EmployeeCategory.objects.get_or_create(name="Staff")[0]
    emp = Employee.objects.create(
        employee_number=emp_no, full_name="Test Person", email=email,
        date_of_joining="2024-01-01", bank_name="BOC",
        bank_account_name="Test", bank_branch_name="CMB",
        branch=branch, category=cat,
    )
    emp.refresh_from_db()
    emp.user.set_password("Pass!word99")
    emp.user.save()
    emp.must_change_password = False
    emp.save()
    return emp


def _make_paysheet(employee, month=1, year=2025):
    return PaySheet.objects.create(
        employee=employee,
        category_snapshot=employee.category,
        month=month, year=year,
        breakdown={"Basic Salary": "50000.00", "HRA": "5000.00"},
        gross_total=Decimal("55000.00"),
    )


@override_settings(RATELIMIT_ENABLE=False)
class TestDashboard(TestCase):
    def setUp(self):
        self.emp = _make_employee("dash@test.com", "EMP010")
        self.client.login(username="dash@test.com", password="Pass!word99")

    def test_dashboard_renders_for_employee(self):
        resp = self.client.get(reverse("payroll:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "payroll/dashboard.html")

    def test_dashboard_lists_own_paysheets(self):
        _make_paysheet(self.emp, month=1, year=2025)
        _make_paysheet(self.emp, month=2, year=2025)
        resp = self.client.get(reverse("payroll:dashboard"))
        self.assertEqual(len(resp.context["entries"]), 2)

    def test_dashboard_filters_by_month_and_year(self):
        _make_paysheet(self.emp, month=1, year=2025)
        _make_paysheet(self.emp, month=2, year=2026)

        resp = self.client.get(reverse("payroll:dashboard"), {"month": "2", "year": "2026"})

        self.assertEqual(len(resp.context["entries"]), 1)
        self.assertEqual(resp.context["entries"][0]["month"], 2)
        self.assertTrue(resp.context["filters_applied"])

    def test_dashboard_filter_empty_result_message(self):
        _make_paysheet(self.emp, month=1, year=2025)

        resp = self.client.get(reverse("payroll:dashboard"), {"month": "2", "year": "2025"})

        self.assertEqual(len(resp.context["entries"]), 0)
        self.assertContains(resp, "No paysheet found for the selected month/year.")

    def test_dashboard_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("payroll:dashboard"), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp["Location"])

    def test_dashboard_does_not_show_other_employee_paysheets(self):
        other = _make_employee("other@test.com", "EMP011")
        _make_paysheet(other, month=3, year=2025)
        resp = self.client.get(reverse("payroll:dashboard"))
        self.assertEqual(len(resp.context["entries"]), 0)

    def test_admin_session_redirects_to_employee_login(self):
        self.client.logout()
        admin_user = User.objects.create_superuser(
            "admin@test.com", "admin@test.com", "Admin!Pass123"
        )
        self.client.login(username=admin_user.username, password="Admin!Pass123")
        resp = self.client.get(reverse("payroll:dashboard"), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])


@override_settings(RATELIMIT_ENABLE=False)
class TestPayslipDetail(TestCase):
    def setUp(self):
        self.emp_a = _make_employee("empa@test.com", "EMP020")
        self.emp_b = _make_employee("empb@test.com", "EMP021")
        self.ps_a = _make_paysheet(self.emp_a)
        self.ps_b = _make_paysheet(self.emp_b)

    def test_employee_can_view_own_payslip(self):
        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(
            reverse("payroll:payslip_detail", kwargs={"uuid": self.ps_a.id})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "payroll/payslip_detail.html")

    def test_idor_employee_a_cannot_access_employee_b_payslip(self):
        """
        CRITICAL: Even with a valid UUID, employee A must not see employee B's payslip.
        The ownership check must run independently of URL guessability.
        """
        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(
            reverse("payroll:payslip_detail", kwargs={"uuid": self.ps_b.id})
        )
        self.assertEqual(resp.status_code, 403)

    def test_nonexistent_uuid_returns_403_not_404(self):
        """Returns 403 so attackers cannot distinguish missing from forbidden."""
        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(
            reverse("payroll:payslip_detail", kwargs={"uuid": uuid.uuid4()})
        )
        self.assertEqual(resp.status_code, 403)

    def test_payslip_detail_requires_login(self):
        resp = self.client.get(
            reverse("payroll:payslip_detail", kwargs={"uuid": self.ps_a.id}), follow=False
        )
        self.assertEqual(resp.status_code, 302)

    def test_print_view_ownership_enforced(self):
        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(
            reverse("payroll:payslip_print", kwargs={"uuid": self.ps_b.id})
        )
        self.assertEqual(resp.status_code, 403)

    def test_breakdown_rows_in_context(self):
        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(
            reverse("payroll:payslip_detail", kwargs={"uuid": self.ps_a.id})
        )
        self.assertIn("breakdown_rows", resp.context)
        self.assertEqual(len(resp.context["breakdown_rows"]), 2)

    def test_many_components_flag_set_when_over_15(self):
        big_breakdown = {f"Component {i}": str(1000 * i) for i in range(1, 20)}
        ps = PaySheet.objects.create(
            employee=self.emp_a, category_snapshot=self.emp_a.category,
            month=6, year=2025, breakdown=big_breakdown,
            gross_total=Decimal("190000"),
        )
        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(
            reverse("payroll:payslip_print", kwargs={"uuid": ps.id})
        )
        self.assertTrue(resp.context["many_components"])

    def test_print_all_lists_only_own_payslips(self):
        _make_paysheet(self.emp_a, month=2, year=2025)
        _make_paysheet(self.emp_b, month=3, year=2025)

        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(reverse("payroll:payslip_print_all"))

        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "payroll/payslip_print_all.html")
        self.assertEqual(len(resp.context["entries"]), 2)
        self.assertContains(resp, "January 2025")
        self.assertContains(resp, "February 2025")
        self.assertNotContains(resp, "March 2025")

    def test_print_all_requires_login(self):
        resp = self.client.get(reverse("payroll:payslip_print_all"), follow=False)
        self.assertEqual(resp.status_code, 302)

    def test_download_all_returns_pdf_for_own_payslips(self):
        _make_paysheet(self.emp_a, month=2, year=2025)
        _make_paysheet(self.emp_b, month=3, year=2025)

        self.client.login(username="empa@test.com", password="Pass!word99")
        resp = self.client.get(reverse("payroll:payslip_download_all"))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("EMP020-payslips.pdf", resp["Content-Disposition"])
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertGreater(len(resp.content), 1000)

    def test_download_all_requires_login(self):
        resp = self.client.get(reverse("payroll:payslip_download_all"), follow=False)
        self.assertEqual(resp.status_code, 302)
