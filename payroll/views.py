"""
Employee self-service portal views.

Views:
    dashboard         - Lists all payslip months available to the logged-in employee
    payslip_detail    - Shows breakdown for one payslip (UUID URL, ownership enforced)
    payslip_print     - Print-optimised view of the same payslip (A4, one page)
    payslip_print_all - Print-optimised view for all of the employee's payslips
    payslip_download_all - Server-generated PDF for all employee payslips

Security:
    Every view that touches a PaySheet calls _get_owned_paysheet() which:
    1. Fetches by UUID (unguessable - IDOR prevention)
    2. Verifies paysheet.employee.user == request.user (defence in depth)
    If either check fails the user receives a 403, never a 404 that would
    confirm existence of another employee's record.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View

from core.constants import MONTHS
from core.mixins import EmployeeRequiredMixin
from .models import PaySheet

logger = logging.getLogger(__name__)


def _get_owned_paysheet(uuid: str, user) -> PaySheet:
    """
    Fetch a PaySheet by UUID and enforce ownership.

    Raises PermissionDenied (403) if:
    - The UUID does not exist
    - The paysheet belongs to a different employee

    We deliberately return 403 (not 404) for non-existent UUIDs so that
    attackers cannot distinguish "wrong UUID" from "not your record".
    """
    try:
        paysheet = PaySheet.objects.select_related(
            "employee", "employee__user", "category_snapshot"
        ).get(pk=uuid)
    except PaySheet.DoesNotExist:
        raise PermissionDenied

    if not hasattr(user, "employee") or paysheet.employee.user_id != user.pk:
        logger.warning(
            "IDOR attempt: user %s tried to access paysheet %s (owner: %s).",
            user.username,
            uuid,
            paysheet.employee.email,
        )
        raise PermissionDenied

    return paysheet


def _breakdown_rows(paysheet: PaySheet) -> List[Dict[str, Decimal]]:
    rows = []
    for label, amount in paysheet.breakdown.items():
        try:
            amount_dec = Decimal(str(amount))
        except InvalidOperation:
            amount_dec = Decimal("0")
        rows.append({"label": label, "amount": amount_dec})
    return rows


class DashboardView(EmployeeRequiredMixin, View):
    """
    Employee's payslip dashboard.

    Shows all payslip months available, most recent first.
    Each entry is a link to the payslip detail view.
    """

    template_name = "payroll/dashboard.html"

    def get(self, request):
        paysheets = (
            PaySheet.objects
            .filter(employee=request.user.employee)
            .order_by("-year", "-month")
            .only("id", "month", "year", "gross_total", "updated_at")
        )

        months_map = dict(MONTHS)
        entries = [
            {
                "uuid": str(ps.id),
                "month_name": months_map.get(ps.month, str(ps.month)),
                "month": ps.month,
                "year": ps.year,
                "gross_total": ps.gross_total,
                "updated_at": ps.updated_at,
            }
            for ps in paysheets
        ]

        return render(request, self.template_name, {
            "entries": entries,
            "employee": request.user.employee,
        })


class PayslipDetailView(EmployeeRequiredMixin, View):
    """
    Renders the full salary breakdown for one payslip month.

    URL uses the PaySheet UUID - unguessable, never a sequential integer.
    Ownership is enforced by _get_owned_paysheet().
    """

    template_name = "payroll/payslip_detail.html"

    def get(self, request, uuid):
        paysheet = _get_owned_paysheet(uuid, request.user)
        months_map = dict(MONTHS)

        return render(request, self.template_name, {
            "paysheet": paysheet,
            "breakdown_rows": _breakdown_rows(paysheet),
            "month_name": months_map.get(paysheet.month, str(paysheet.month)),
            "employee": paysheet.employee,
        })


class PayslipPrintView(EmployeeRequiredMixin, View):
    """
    Print-optimised payslip view.

    Uses a minimal template with A4 print CSS. The design guarantees
    the entire payslip fits on exactly one A4 page regardless of how
    many salary components exist (5 or 35).
    """

    template_name = "payroll/payslip_print.html"

    def get(self, request, uuid):
        paysheet = _get_owned_paysheet(uuid, request.user)
        breakdown_rows = _breakdown_rows(paysheet)
        months_map = dict(MONTHS)

        return render(request, self.template_name, {
            "paysheet": paysheet,
            "breakdown_rows": breakdown_rows,
            "month_name": months_map.get(paysheet.month, str(paysheet.month)),
            "employee": paysheet.employee,
            "many_components": len(breakdown_rows) > 15,
        })


class PayslipPrintAllView(EmployeeRequiredMixin, View):
    """Print all payslips belonging to the logged-in employee."""

    template_name = "payroll/payslip_print_all.html"

    def get(self, request):
        paysheets = (
            PaySheet.objects
            .filter(employee=request.user.employee)
            .select_related("employee", "category_snapshot", "employee__branch")
            .order_by("-year", "-month")
        )
        months_map = dict(MONTHS)
        entries = [
            {
                "paysheet": paysheet,
                "breakdown_rows": _breakdown_rows(paysheet),
                "month_name": months_map.get(paysheet.month, str(paysheet.month)),
                "many_components": len(paysheet.breakdown) > 15,
            }
            for paysheet in paysheets
        ]

        return render(request, self.template_name, {
            "entries": entries,
            "employee": request.user.employee,
        })


class PayslipDownloadAllView(EmployeeRequiredMixin, View):
    """Download all payslips belonging to the logged-in employee as one PDF."""

    def get(self, request):
        paysheets = list(
            PaySheet.objects
            .filter(employee=request.user.employee)
            .select_related("employee", "category_snapshot", "employee__branch")
            .order_by("-year", "-month")
        )

        from payroll.services.pdf_service import build_payslips_pdf

        pdf_bytes = build_payslips_pdf(paysheets)
        filename = f"{request.user.employee.employee_number}-payslips.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
