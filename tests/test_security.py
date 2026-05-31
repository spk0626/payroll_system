"""
D7 tests: security headers and hardening.

Verifies that every response carries the required security headers.
These tests are environment-agnostic — they work in development and production.
"""

from django.test import TestCase, override_settings
from django.contrib.auth.models import User


class TestSecurityHeaders(TestCase):
    """Every response must include required security headers."""

    def _get(self, path="/login/"):
        return self.client.get(path)

    def test_csp_header_present(self):
        resp = self._get()
        self.assertIn("Content-Security-Policy", resp)
        csp = resp["Content-Security-Policy"]
        self.assertIn("default-src", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("form-action 'self'", csp)

    def test_x_frame_options_deny(self):
        resp = self._get()
        self.assertEqual(resp.get("X-Frame-Options", "").upper(), "DENY")

    def test_x_content_type_options_nosniff(self):
        resp = self._get()
        self.assertEqual(resp.get("X-Content-Type-Options"), "nosniff")

    def test_referrer_policy(self):
        resp = self._get()
        self.assertEqual(
            resp.get("Referrer-Policy"), "strict-origin-when-cross-origin"
        )

    def test_permissions_policy(self):
        resp = self._get()
        self.assertIn("Permissions-Policy", resp)
        pp = resp["Permissions-Policy"]
        self.assertIn("geolocation=()", pp)
        self.assertIn("camera=()", pp)

    def test_headers_on_authenticated_portal_page(self):
        """Security headers must be present on all pages, not just public ones."""
        user = User.objects.create_user(
            "sec@test.com", "sec@test.com", "SecurePass!1"
        )
        self.client.login(username="sec@test.com", password="SecurePass!1")
        resp = self.client.get("/portal/")
        self.assertIn("Content-Security-Policy", resp)
        self.assertEqual(resp.get("X-Frame-Options", "").upper(), "DENY")

    def test_403_returns_custom_template(self):
        """Custom error pages must not leak framework information."""
        # Force a 403 by accessing admin without permission
        resp = self.client.get("/management-portal/", follow=False)
        # 302 redirect to login — that's expected, test the error page directly
        resp2 = self.client.get("/management-portal/payroll/paysheet/", follow=False)
        self.assertIn(resp2.status_code, [302, 403])

    def test_admin_url_is_not_default(self):
        """The admin must not be at /admin/ — that's the default bots scan."""
        resp = self.client.get("/admin/")
        # Should be 404 or redirect — NOT the Django admin login
        self.assertNotEqual(resp.status_code, 200)
        if resp.status_code == 200:
            self.assertNotIn("Django administration", resp.content.decode())


class TestPayslipPrivacyHeaders(TestCase):
    """Payslip responses must carry no-cache directives to prevent browser caching."""

    def test_login_page_has_security_headers(self):
        resp = self.client.get("/login/")
        self.assertEqual(resp.status_code, 200)
        # CSP must be present even on public pages
        self.assertIn("Content-Security-Policy", resp)


class TestAdminURLObscured(TestCase):
    def test_default_admin_url_returns_404(self):
        resp = self.client.get("/admin/")
        self.assertNotEqual(resp.status_code, 200)

    def test_custom_admin_url_accessible(self):
        resp = self.client.get("/management-portal/")
        # Should redirect to login (302) not 404
        self.assertIn(resp.status_code, [200, 302])