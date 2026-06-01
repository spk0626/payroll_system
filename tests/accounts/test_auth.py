"""
Tests for D2: authentication, middleware, and access control.

Coverage:
- Login: valid credentials, invalid credentials
- Remember me: session expiry set correctly
- Logout: POST-only; GET redirects
- ForcePasswordChangeMiddleware: redirects employees with flag set
- SessionIdleTimeoutMiddleware: logs out after idle timeout
- ChangePasswordView: clears must_change_password flag on success
- Password reset: form acceptance, always-success response (no enumeration)

Note on rate limiting:
    django-ratelimit uses the cache backend. Tests that hit the login view
    multiple times within a test run may trigger the rate limit. We use
    @override_settings to disable rate-limiting for login tests that don't
    specifically test the rate limit, keeping tests independent and reliable.
"""

import time

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings, RequestFactory
from django.urls import reverse

from employees.models import Branch, Employee, EmployeeCategory


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_employee(email="emp@test.com", emp_number="EMP001"):
    branch = Branch.objects.get_or_create(name="Test Branch")[0]
    category = EmployeeCategory.objects.get_or_create(name="Test Category")[0]
    emp = Employee.objects.create(
        employee_number=emp_number,
        full_name="Test Employee",
        email=email,
        date_of_joining="2024-01-01",
        bank_name="BOC",
        bank_account_name="Test Employee",
        bank_branch_name="Colombo",
        branch=branch,
        category=category,
    )
    emp.refresh_from_db()
    return emp


def _make_admin(username="admin@test.com"):
    return User.objects.create_user(
        username=username,
        email=username,
        password="Admin!Pass123",
        is_staff=True,
    )


# ─── Login ────────────────────────────────────────────────────────────────────

# Disable rate limiting for login tests that test functional behaviour,
# not rate-limit behaviour. This keeps tests isolated and deterministic.
@override_settings(RATELIMIT_ENABLE=False)
class TestLoginView(TestCase):
    def setUp(self):
        self.emp = _make_employee()
        self.emp.refresh_from_db()
        self.emp.user.set_password("MyPass!1234")
        self.emp.user.save()
        # Clear force-change so we test pure login flow
        self.emp.must_change_password = False
        self.emp.save()

    def _login(self, email="emp@test.com", password="MyPass!1234", remember=False):
        data = {"username": email, "password": password}
        if remember:
            data["remember_me"] = "on"
        return self.client.post(reverse("accounts:login"), data, follow=False)

    def test_valid_login_redirects_to_portal(self):
        resp = self._login()
        self.assertRedirects(resp, reverse("payroll:dashboard"), fetch_redirect_response=False)

    def test_invalid_password_returns_form_with_error(self):
        resp = self._login(password="wrongpassword")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/login.html")
        self.assertTrue(resp.context["form"].errors)

    def test_invalid_email_returns_form_with_error(self):
        resp = self._login(email="nobody@test.com")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["form"].errors)

    def test_get_login_page_renders(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/login.html")

    def test_already_logged_in_redirects(self):
        self._login()
        resp = self.client.get(reverse("accounts:login"))
        self.assertRedirects(resp, reverse("payroll:dashboard"), fetch_redirect_response=False)

    def test_admin_login_redirects_to_admin(self):
        _make_admin("admin@test.com")
        resp = self.client.post(
            reverse("accounts:login"),
            {"username": "admin@test.com", "password": "Admin!Pass123"},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("management-portal", resp["Location"])

    def test_remember_me_sets_long_expiry(self):
        self._login(remember=True)
        # Session expiry should be set to SESSION_REMEMBER_ME_AGE, not 0.
        # We verify the session does not expire at browser close.
        session = self.client.session
        # set_expiry(0) → expires at browser close; set_expiry(N) → N seconds
        # Django's get_expiry_age() returns the age in seconds.
        age = session.get_expiry_age()
        self.assertGreater(age, 60 * 60 * 24, "Remember me should give > 1 day session")

    def test_no_remember_me_browser_close_expiry(self):
        self._login(remember=False)
        session = self.client.session
        # When set_expiry(0) is called, Django expires the session at browser close.
        # The session's _session_expiry key is 0 in this case.
        expiry_value = session.get("_session_expiry", None)
        # 0 means browser-close; None means using default (also browser-close here)
        self.assertIn(expiry_value, [0, None])


# ─── Logout ───────────────────────────────────────────────────────────────────

class TestLogoutView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@test.com", password="Pass!word123", is_active=True
        )
        self.client.login(username="user@test.com", password="Pass!word123")

    def test_post_logout_ends_session(self):
        resp = self.client.post(reverse("accounts:logout"), follow=False)
        self.assertRedirects(resp, reverse("accounts:login"), fetch_redirect_response=False)
        resp2 = self.client.get(reverse("accounts:login"))
        self.assertFalse(resp2.wsgi_request.user.is_authenticated)

    def test_get_logout_redirects_to_login(self):
        resp = self.client.get(reverse("accounts:logout"))
        self.assertRedirects(resp, reverse("accounts:login"), fetch_redirect_response=False)


# ─── ForcePasswordChangeMiddleware ────────────────────────────────────────────

@override_settings(RATELIMIT_ENABLE=False)
class TestForcePasswordChangeMiddleware(TestCase):
    def setUp(self):
        self.emp = _make_employee(email="force@test.com", emp_number="EMP002")
        self.emp.refresh_from_db()
        self.emp.user.set_password("TempPass!12")
        self.emp.user.save()
        # must_change_password is True by default

    def test_redirected_to_change_password_on_portal(self):
        self.client.login(username="force@test.com", password="TempPass!12")
        resp = self.client.get(reverse("payroll:dashboard"), follow=False)
        self.assertRedirects(
            resp, reverse("accounts:change_password"), fetch_redirect_response=False
        )

    def test_change_password_page_itself_is_accessible(self):
        self.client.login(username="force@test.com", password="TempPass!12")
        resp = self.client.get(reverse("accounts:change_password"))
        self.assertEqual(resp.status_code, 200)

    def test_no_redirect_after_flag_cleared(self):
        self.emp.must_change_password = False
        self.emp.save()
        self.client.login(username="force@test.com", password="TempPass!12")
        resp = self.client.get(reverse("payroll:dashboard"), follow=False)
        location = resp.get("Location", "")
        self.assertNotIn("change-password", location)

    def test_admin_not_affected_by_middleware(self):
        admin = _make_admin("admin2@test.com")
        self.client.login(username="admin2@test.com", password="Admin!Pass123")
        resp = self.client.get("/management-portal/", follow=False)
        location = resp.get("Location", "")
        self.assertNotIn("change-password", location)


# ─── ChangePasswordView ───────────────────────────────────────────────────────

class TestChangePasswordView(TestCase):
    def setUp(self):
        self.emp = _make_employee(email="change@test.com", emp_number="EMP003")
        self.emp.refresh_from_db()
        self.emp.user.set_password("OldPass!12")
        self.emp.user.save()

    def test_change_password_clears_must_change_flag(self):
        self.client.login(username="change@test.com", password="OldPass!12")
        self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": "OldPass!12",
                "new_password1": "NewSecure!99",
                "new_password2": "NewSecure!99",
            },
        )
        self.emp.refresh_from_db()
        self.assertFalse(self.emp.must_change_password)

    def test_change_password_keeps_user_logged_in(self):
        self.client.login(username="change@test.com", password="OldPass!12")
        resp = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": "OldPass!12",
                "new_password1": "NewSecure!99",
                "new_password2": "NewSecure!99",
            },
            follow=True,
        )
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_mismatched_passwords_returns_errors(self):
        self.client.login(username="change@test.com", password="OldPass!12")
        resp = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": "OldPass!12",
                "new_password1": "NewSecure!99",
                "new_password2": "DifferentPass!99",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["form"].errors)


# ─── Password reset ───────────────────────────────────────────────────────────

@override_settings(RATELIMIT_ENABLE=False)
class TestPasswordResetRequestView(TestCase):
    def test_get_renders_form(self):
        resp = self.client.get(reverse("accounts:password_reset"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "accounts/password_reset_request.html")

    def test_post_with_valid_email_redirects_to_login(self):
        User.objects.create_user(
            username="reset@test.com", email="reset@test.com", password="Abc!12345678"
        )
        resp = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "reset@test.com"},
            follow=False,
        )
        self.assertRedirects(resp, reverse("accounts:login"), fetch_redirect_response=False)

    def test_post_with_unknown_email_also_redirects_to_login(self):
        """Non-existent email must return the same response — prevents enumeration."""
        resp = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "nobody@unknown.com"},
            follow=False,
        )
        self.assertRedirects(resp, reverse("accounts:login"), fetch_redirect_response=False)


# ─── Session idle timeout ─────────────────────────────────────────────────────

@override_settings(SESSION_IDLE_TIMEOUT=1)
class TestSessionIdleTimeout(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="idle@test.com", password="Pass!word99", is_active=True
        )

    def test_idle_session_is_terminated(self):
        self.client.login(username="idle@test.com", password="Pass!word99")
        session = self.client.session
        session["_last_activity"] = time.time() - 10  # 10s ago > 1s timeout
        session.save()
        resp = self.client.get(reverse("accounts:login"), follow=False)
        # Should be logged out and redirected to login
        self.assertRedirects(resp, reverse("accounts:login"), fetch_redirect_response=False)

    def test_active_session_not_terminated(self):
        self.client.login(username="idle@test.com", password="Pass!word99")
        session = self.client.session
        session["_last_activity"] = time.time()
        session.save()
        # Already logged in → redirected to portal, not kicked out
        resp = self.client.get(reverse("accounts:login"), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn(reverse("accounts:login"), resp.get("Location", ""))

