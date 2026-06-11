"""
PDF generation for employee payslips.

The employee portal uses browser print for interactive preview, but downloads
must be generated server-side so the result is reliable across browsers/printers.
"""

from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Dict, List

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core.constants import MONTHS


def build_payslips_pdf(paysheets) -> bytes:
    """Return a PDF containing one A4 page per payslip."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    for paysheet in paysheets:
        _draw_payslip_page(pdf, paysheet)
        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


def _draw_payslip_page(pdf, paysheet) -> None:
    width, height = A4
    margin = 1.2 * cm
    y = height - margin
    employee = paysheet.employee
    month_name = dict(MONTHS).get(paysheet.month, str(paysheet.month))
    currency = getattr(settings, "CURRENCY_SYMBOL", "LKR")

    primary = colors.HexColor("#005f73")
    pdf.setStrokeColor(primary)
    pdf.setLineWidth(1.5)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin, y, settings.COMPANY_NAME)
    _draw_logo(pdf, width - margin - 64, y - 30)
    pdf.setFont("Helvetica", 9)
    if getattr(settings, "COMPANY_ADDRESS", ""):
        pdf.drawString(margin, y - 11, settings.COMPANY_ADDRESS)
    pdf.line(margin, y - 24, width - margin, y - 24)

    y -= 42
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(width / 2, y, "SALARY PAYSLIP")
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2, y - 10, f"{month_name} {paysheet.year}")

    y -= 34
    _draw_info_box(pdf, paysheet, margin, y, width - (2 * margin))

    y -= 60
    rows = _breakdown_rows(paysheet)
    row_height = 18 if len(rows) <= 15 else 12
    font_size = 10 if len(rows) <= 15 else 8
    table_width = width - (2 * margin)
    amount_x = width - margin - 4

    pdf.setFillColor(primary)
    pdf.rect(margin, y - row_height, table_width, row_height, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin + 5, y - 12, "DESCRIPTION")
    pdf.drawRightString(amount_x, y - 12, f"AMOUNT ({currency})")
    y -= row_height

    pdf.setFont("Helvetica", font_size)
    for index, row in enumerate(rows):
        fill = colors.white if index % 2 == 0 else colors.HexColor("#f0f0f0")
        pdf.setFillColor(fill)
        pdf.rect(margin, y - row_height, table_width, row_height, fill=1, stroke=0)
        pdf.setFillColor(colors.black)
        pdf.drawString(margin + 5, y - row_height + 5, _clip(row["label"], 70))
        pdf.drawRightString(amount_x, y - row_height + 5, f"{row['amount']:.2f}")
        y -= row_height

    pdf.setFillColor(primary)
    pdf.rect(margin, y - 18, table_width, 18, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin + 5, y - 13, "Gross Total")
    pdf.drawRightString(amount_x, y - 13, f"{currency} {paysheet.gross_total:.2f}")

    pdf.setFillColor(colors.HexColor("#777777"))
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(margin, margin, f"Confidential - Intended solely for {employee.full_name}. Do not distribute.")


def _draw_info_box(pdf, paysheet, x, y, width) -> None:
    employee = paysheet.employee
    pdf.setFillColor(colors.HexColor("#f5f5f5"))
    pdf.setStrokeColor(colors.HexColor("#d0d0d0"))
    pdf.rect(x, y - 56, width, 56, fill=1, stroke=1)

    left = [
        ("Employee No:", employee.employee_number),
        ("Name:", employee.full_name),
        ("Bank:", f"{employee.bank_name} - {employee.bank_branch_name}"),
        ("Account No:", getattr(employee, "bank_account_number", "") or "-"),
    ]
    right = [
        ("Category:", paysheet.category_snapshot.name if paysheet.category_snapshot else "-"),
        ("Branch:", employee.branch.name),
        ("Account Name:", employee.bank_account_name),
    ]
    _draw_pairs(pdf, left, x + 8, y - 12)
    _draw_pairs(pdf, right, x + (width / 2) + 8, y - 12)


def _draw_pairs(pdf, pairs, x, y) -> None:
    for label, value in pairs:
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(x, y, label)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x + 64, y, _clip(str(value), 38))
        y -= 12


def _draw_logo(pdf, x, y) -> None:
    try:
        from core.models import CompanySetting

        setting = CompanySetting.load()
        if setting.logo:
            pdf.drawImage(ImageReader(setting.logo.path), x, y, width=64, height=42, preserveAspectRatio=True, mask="auto")
            return
    except Exception:
        pass

    pdf.setFillColor(colors.HexColor("#005f73"))
    pdf.rect(x + 16, y, 42, 42, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(x + 37, y + 16, "SA")


def _breakdown_rows(paysheet) -> List[Dict]:
    rows = []
    for label, amount in paysheet.breakdown.items():
        try:
            amount_dec = Decimal(str(amount))
        except InvalidOperation:
            amount_dec = Decimal("0")
        rows.append({"label": label, "amount": amount_dec})
    return rows


def _clip(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3] + "..."
