"""
Authentication views for Syntax Asia Salary System.

Views:
    LoginView        — rate-limited email+password login with Remember Me and show-password
    LogoutView       — POST-only logout (CSRF protected)
    ChangePasswordView — force-change on first login + voluntary changes
    PasswordResetRequestView — forgot password: sends email with reset link
    PasswordResetConfirmView — consumes signed token, sets new password

Security decisions:
    - Login is rate-limited per IP (django-ratelimit): 5 attempts / 15 minutes.
    - All forms use Django's CSRF middleware (active by default).
    - Password reset tokens are Django's signed tokens: single-use, 24-hour expiry.
    - "Show password" is JavaScript-only (no server involvement).
    - "Remember Me" uses request.session.set_expiry() — server-side only.
    - The password reset endpoint is also rate-limited to prevent enumeration.
"""

import logging

from django.conf import settings
from django.contrib import auth, messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetConfirmView as DjangoPasswordResetConfirmView
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django_ratelimit.decorators import ratelimit

logger = logging.getLogger(__name__)


# ─── Login ────────────────────────────────────────────────────────────────────

class LoginView(View):
    """
    Email + password login with:
    - IP-based rate limiting (5 attempts per 15 minutes)
    - "Remember Me" checkbox (session persists 30 days vs browser-close)
    - Show/hide password toggle (handled in template JS)
    """

    template_name = "accounts/login.html"

    @method_decorator(ratelimit(key="ip", rate="5/15m", method="POST", block=False))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return render(request, self.template_name, {"form": AuthenticationForm()})

    def post(self, request):
        # django-ratelimit sets this attribute when the limit is exceeded.
        if getattr(request, "limited", False):
            messages.error(
                request,
                "Too many login attempts. Please wait 15 minutes before trying again.",
            )
            return render(request, self.template_name, {"form": AuthenticationForm()}, status=429)

        form = AuthenticationForm(request, data=request.POST)
        if not form.is_valid():
            logger.warning(
                "Failed login attempt for username '%s' from IP %s.",
                request.POST.get("username", ""),
                _get_client_ip(request),
            )
            return render(request, self.template_name, {"form": form})

        user = form.get_user()
        auth.login(request, user)

        # Remember Me: extend session to 30 days, otherwise expires on browser close.
        if request.POST.get("remember_me"):
            request.session.set_expiry(settings.SESSION_REMEMBER_ME_AGE)
        else:
            request.session.set_expiry(0)  # Expires when browser closes

        logger.info("Successful login for user %s.", user.username)

        # Redirect admins to the admin panel, employees to the portal.
        if user.is_staff or user.is_superuser:
            return redirect(f"/{settings.ADMIN_URL}")
        return redirect(settings.LOGIN_REDIRECT_URL)


# ─── Logout ───────────────────────────────────────────────────────────────────

class LogoutView(View):
    """
    POST-only logout. GET requests are redirected to login.
    Using POST prevents CSRF-based forced logout from external pages.
    """

    def post(self, request):
        auth.logout(request)
        messages.success(request, "You have been logged out.")
        return redirect(settings.LOGOUT_REDIRECT_URL)

    def get(self, request):
        return redirect(settings.LOGIN_URL)


# ─── Change password ──────────────────────────────────────────────────────────

class ChangePasswordView(View):
    """
    Password change for:
    1. First-login force-change (must_change_password=True on Employee)
    2. Voluntary change by a logged-in employee

    On success:
    - Clears must_change_password flag.
    - Calls update_session_auth_hash so the user is NOT logged out.
    - Redirects to the portal dashboard.
    """

    template_name = "accounts/change_password.html"

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        form = PasswordChangeForm(user=request.user)
        return render(request, self.template_name, self._ctx(request, form))

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)

        form = PasswordChangeForm(user=request.user, data=request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._ctx(request, form))

        form.save()
        # Keep the user logged in after a password change.
        update_session_auth_hash(request, form.user)

        # Clear the force-change flag on the employee profile.
        employee = getattr(request.user, "employee", None)
        if employee and employee.must_change_password:
            employee.must_change_password = False
            employee.save(update_fields=["must_change_password", "updated_at"])
            messages.success(
                request,
                "Password updated. Welcome to your payslip portal!",
            )
        else:
            messages.success(request, "Password changed successfully.")

        logger.info("Password changed for user %s.", request.user.username)
        return redirect(settings.LOGIN_REDIRECT_URL)

    def _ctx(self, request, form) -> dict:
        employee = getattr(request.user, "employee", None)
        is_forced = bool(employee and employee.must_change_password)
        return {"form": form, "is_forced_change": is_forced}


# ─── Forgot password (request reset) ──────────────────────────────────────────

class PasswordResetRequestView(View):
    """
    Accepts an email address and sends a password reset link.

    Rate-limited to prevent email enumeration and abuse.
    Always shows the same success message regardless of whether the
    email exists — prevents user enumeration.
    """

    template_name = "accounts/password_reset_request.html"
    email_template = "accounts/email/password_reset.html"
    subject = "Reset your payslip portal password"

    @method_decorator(ratelimit(key="ip", rate="3/15m", method="POST", block=False))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return render(request, self.template_name, {"form": PasswordResetForm()})

    def post(self, request):
        if getattr(request, "limited", False):
            messages.error(request, "Too many requests. Please wait 15 minutes.")
            return render(request, self.template_name, {"form": PasswordResetForm()}, status=429)

        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="accounts/email/password_reset.txt",
                html_email_template_name=self.email_template,
                subject_template_name="accounts/email/password_reset_subject.txt",
            )

        # Always show success — never reveal whether the email exists.
        messages.success(
            request,
            "If that email address is registered, you will receive a reset link shortly. "
            "Check your inbox (and spam folder).",
        )
        return redirect("accounts:login")


# ─── Password reset confirm ───────────────────────────────────────────────────

class PasswordResetConfirmView(DjangoPasswordResetConfirmView):
    """
    Consumes the signed reset token from the email link and sets a new password.

    Extends Django's built-in view with:
    - Custom template
    - Redirect to login with a success message
    - Clears must_change_password if it was set (edge case: admin reset + employee
      has not yet done their first-login change)
    """

    template_name = "accounts/password_reset_confirm.html"
    success_url = None  # We handle redirect manually for the message.

    def form_valid(self, form):
        user = form.save()
        # Clear force-change flag in case it was set.
        employee = getattr(user, "employee", None)
        if employee and employee.must_change_password:
            employee.must_change_password = False
            employee.save(update_fields=["must_change_password", "updated_at"])

        logger.info("Password reset completed for user %s.", user.username)
        messages.success(
            self.request,
            "Your password has been reset. You can now log in with your new password.",
        )
        return redirect("accounts:login")


# ─── MFA setup (admin only) ───────────────────────────────────────────────────

class MFASetupView(View):
    """
    TOTP MFA device setup for admin accounts.

    Generates a QR code for scanning with Google Authenticator / Authy.
    Only accessible to staff/superuser accounts.
    Employees do not use MFA.
    """

    template_name = "accounts/mfa_setup.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect(settings.LOGIN_URL)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        import qrcode
        import qrcode.image.svg
        import io

        # Check if device already exists.
        existing = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()

        qr_svg = None
        device = None

        if not existing:
            # Create an unconfirmed device to generate the QR code.
            device, _ = TOTPDevice.objects.get_or_create(
                user=request.user,
                confirmed=False,
                defaults={"name": f"{request.user.username} TOTP"},
            )
            otpauth_url = device.config_url
            qr = qrcode.make(otpauth_url, image_factory=qrcode.image.svg.SvgImage)
            buf = io.BytesIO()
            qr.save(buf)
            qr_svg = buf.getvalue().decode("utf-8")

        return render(request, self.template_name, {
            "existing_device": existing,
            "device": device,
            "qr_svg": qr_svg,
        })

    def post(self, request):
        """Confirm the TOTP device by verifying the user's first OTP token."""
        from django_otp.plugins.otp_totp.models import TOTPDevice

        token = request.POST.get("token", "").strip()
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()

        if not device:
            messages.error(request, "No pending MFA setup found. Please start again.")
            return redirect("accounts:mfa_setup")

        if device.verify_token(token):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            messages.success(
                request,
                "MFA enabled successfully. Your account is now protected with "
                "two-factor authentication.",
            )
            logger.info("MFA TOTP device confirmed for admin %s.", request.user.username)
            return redirect(f"/{settings.ADMIN_URL}")
        else:
            messages.error(request, "Invalid token. Please check your authenticator app and try again.")
            return redirect("accounts:mfa_setup")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_client_ip(request) -> str:
    """Extract the real client IP, accounting for reverse proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")