"""
Django signals for the employees app.

post_save on Employee:
  Creates a Django User account when a new employee is saved.
  Sets a random secure password and sends a welcome email.

This is deliberately a signal (not logic inside the model's save() method)
so it can be disabled during bulk imports and tested in isolation.
"""

import logging
import secrets
import string

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Employee

logger = logging.getLogger(__name__)


def _generate_secure_password(length: int = 14) -> str:
    """
    Generate a cryptographically secure random password.

    Uses secrets module (not random) for security.
    Guarantees at least one uppercase, one lowercase, one digit,
    and one special character to meet complexity requirements.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure the password meets complexity requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*" for c in password)
        if has_upper and has_lower and has_digit and has_special:
            return password


@receiver(post_save, sender=Employee)
def create_user_account(sender, instance: Employee, created: bool, **kwargs) -> None:
    """
    Create a Django User account when a new Employee is saved.

    Only fires on creation (created=True), not on every save.
    Skips if the employee already has a user account (handles edge cases
    like importing employees with pre-existing accounts).

    The generated password is stored temporarily so it can be displayed
    once to the admin and emailed to the employee.
    """
    if not created:
        return
    if instance.user_id is not None:
        return

    password = _generate_secure_password()

    try:
        user = User.objects.create_user(
            username=instance.email,
            email=instance.email,
            password=password,
            first_name=instance.full_name.split()[0] if instance.full_name else "",
            last_name=" ".join(instance.full_name.split()[1:]) if instance.full_name else "",
            is_active=instance.is_active,
        )
        # Update the employee record with the new user — skip signal to avoid recursion
        Employee.objects.filter(pk=instance.pk).update(user=user)
        instance.user = user

        # Attach the plain-text password to the instance so the admin action
        # can display it once. It is NOT stored anywhere after this point.
        instance._generated_password = password

        logger.info(
            "User account created for employee %s (email: %s).",
            instance.employee_number,
            instance.email,
        )

        # Send welcome email (best-effort; failure is logged, not raised)
        _send_welcome_email(instance, password)

    except Exception:
        logger.exception(
            "Failed to create user account for employee %s.", instance.employee_number
        )


def _send_welcome_email(employee: Employee, password: str) -> None:
    """
    Send a welcome email to the new employee with their login credentials.

    Uses Django's send_mail so the backend is determined by EMAIL_BACKEND
    in settings (console in dev, SMTP in production).
    Best-effort: exceptions are caught and logged, not re-raised.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    from django.template.loader import render_to_string

    try:
        context = {
            "employee": employee,
            "password": password,
            "company_name": settings.COMPANY_NAME,
            "login_url": f"{settings.SITE_URL.rstrip('/')}/login/",
        }
        body = render_to_string("accounts/email/welcome.txt", context)
        send_mail(
            subject=f"Welcome to {settings.COMPANY_NAME} — Your payslip portal account",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[employee.email],
            fail_silently=False,
        )
        logger.info("Welcome email sent to %s.", employee.email)
    except Exception:
        logger.exception(
            "Failed to send welcome email to employee %s.", employee.employee_number
        )
