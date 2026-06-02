"""
Payslip email notification service.

Sends one HTML email per employee per month.
Every send attempt is recorded in EmailLog regardless of outcome.
A single email failure never aborts the batch.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from core.constants import MONTHS, EmailStatus
from payroll.models import EmailLog, PaySheet

logger = logging.getLogger(__name__)


def send_payslip_notifications(paysheets: list[PaySheet], batch_sent_at=None) -> dict:
    """
    Send payslip notification emails to a list of employees.

    Args:
        paysheets:      List of PaySheet objects to notify.
        batch_sent_at:  Timestamp for this send batch. Defaults to now.

    Returns:
        {
            "total": int,
            "sent": int,
            "failed": int,
            "failed_emails": [{"employee": str, "error": str}, ...]
        }

    Design decisions:
    - Each send is wrapped in try/except; failure logged to EmailLog.
    - No exception is raised to the caller on individual failure.
    - Salary data never appears in the email Subject line (it is logged).
    - TLS is enforced by EMAIL_USE_TLS = True in settings.
    """
    if batch_sent_at is None:
        batch_sent_at = timezone.now()

    total = len(paysheets)
    sent = 0
    failed = 0
    failed_emails = []

    for paysheet in paysheets:
        employee = paysheet.employee
        log = _get_or_create_log(paysheet, employee, batch_sent_at)

        try:
            _send_one(paysheet, employee)
            log.status = EmailStatus.SENT
            log.sent_at = timezone.now()
            log.error_message = ""
            log.save(update_fields=["status", "sent_at", "error_message"])
            sent += 1
            logger.info("Payslip email sent to %s.", employee.email)

        except Exception as exc:
            error_msg = str(exc)
            log.status = EmailStatus.FAILED
            log.sent_at = timezone.now()
            log.error_message = error_msg[:1000]
            log.save(update_fields=["status", "sent_at", "error_message"])
            failed += 1
            failed_emails.append({"employee": employee.full_name, "error": error_msg})
            logger.error(
                "Failed to send payslip email to %s: %s", employee.email, error_msg
            )

    logger.info(
        "Payslip batch complete: %d total, %d sent, %d failed.", total, sent, failed
    )
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "failed_emails": failed_emails,
    }


def retry_failed_emails(month: int, year: int) -> dict:
    """
    Retry only the failed EmailLog entries for a given month.

    Never re-sends to employees who already received their email.
    """
    failed_logs = (
        EmailLog.objects
        .filter(paysheet__month=month, paysheet__year=year, status=EmailStatus.FAILED)
        .select_related("paysheet", "paysheet__employee", "paysheet__category_snapshot",
                        "employee")
    )

    paysheets = [log.paysheet for log in failed_logs]
    if not paysheets:
        return {"total": 0, "sent": 0, "failed": 0, "failed_emails": []}

    return send_payslip_notifications(paysheets)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _send_one(paysheet: PaySheet, employee) -> None:
    """
    Compose and send one payslip email.
    Raises on any SMTP error so the caller can log it.
    """
    from decimal import Decimal, InvalidOperation

    months_map = dict(MONTHS)
    month_name = months_map.get(paysheet.month, str(paysheet.month))

    breakdown_rows = []
    for label, amount in paysheet.breakdown.items():
        try:
            breakdown_rows.append({"label": label, "amount": Decimal(str(amount))})
        except InvalidOperation:
            breakdown_rows.append({"label": label, "amount": Decimal("0")})

    context = {
        "employee": employee,
        "paysheet": paysheet,
        "month_name": month_name,
        "breakdown_rows": breakdown_rows,
        "company_name": settings.COMPANY_NAME,
        "company_address": getattr(settings, "COMPANY_ADDRESS", ""),
        "currency_symbol": getattr(settings, "CURRENCY_SYMBOL", "LKR"),
    }

    subject = f"{settings.COMPANY_NAME} — Your payslip for {month_name} {paysheet.year}"
    text_body = render_to_string("email/payslip_notification.txt", context)
    html_body = render_to_string("email/payslip_notification.html", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[employee.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def _get_or_create_log(paysheet, employee, batch_sent_at) -> EmailLog:
    """Get existing EmailLog for this paysheet (for retry) or create a new one."""
    log, _ = EmailLog.objects.get_or_create(
        paysheet=paysheet,
        employee=employee,
        defaults={
            "status": EmailStatus.PENDING,
            "batch_sent_at": batch_sent_at,
        },
    )
    # Update batch timestamp on retry
    log.batch_sent_at = batch_sent_at
    log.status = EmailStatus.PENDING
    log.save(update_fields=["batch_sent_at", "status"])
    return log
