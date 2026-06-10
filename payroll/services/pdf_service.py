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

    pdf.setStrokeColor(colors.HexColor("#1a3a5c"))
    pdf.setLineWidth(1.5)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(margin, y, settings.COMPANY_NAME)
    pdf.setFont("Helvetica", 7)
    if getattr(settings, "COMPANY_ADDRESS", ""):
        pdf.drawString(margin, y - 11, settings.COMPANY_ADDRESS)
    pdf.line(margin, y - 24, width - margin, y - 24)

    y -= 42
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(width / 2, y, "SALARY PAYSLIP")
    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(width / 2, y - 10, f"{month_name} {paysheet.year}")

    y -= 34
    _draw_info_box(pdf, paysheet, margin, y, width - (2 * margin))

    y -= 60
    rows = _breakdown_rows(paysheet)
    row_height = 13 if len(rows) <= 15 else 10
    font_size = 7.5 if len(rows) <= 15 else 6.5
    table_width = width - (2 * margin)
    amount_x = width - margin - 4

    pdf.setFillColor(colors.HexColor("#333333"))
    pdf.rect(margin, y - row_height, table_width, row_height, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(margin + 5, y - 9, "DESCRIPTION")
    pdf.drawRightString(amount_x, y - 9, f"AMOUNT ({currency})")
    y -= row_height

    pdf.setFont("Helvetica", font_size)
    for index, row in enumerate(rows):
        fill = colors.white if index % 2 == 0 else colors.HexColor("#f0f0f0")
        pdf.setFillColor(fill)
        pdf.rect(margin, y - row_height, table_width, row_height, fill=1, stroke=0)
        pdf.setFillColor(colors.black)
        pdf.drawString(margin + 5, y - row_height + 3, _clip(row["label"], 70))
        pdf.drawRightString(amount_x, y - row_height + 3, f"{row['amount']:.2f}")
        y -= row_height

    pdf.setFillColor(colors.HexColor("#333333"))
    pdf.rect(margin, y - 16, table_width, 16, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(margin + 5, y - 11, "Gross Total")
    pdf.drawRightString(amount_x, y - 11, f"{currency} {paysheet.gross_total:.2f}")

    pdf.setFillColor(colors.HexColor("#777777"))
    pdf.setFont("Helvetica-Oblique", 6)
    pdf.drawString(margin, margin, f"Confidential - Intended solely for {employee.full_name}. Do not distribute.")


def _draw_info_box(pdf, paysheet, x, y, width) -> None:
    employee = paysheet.employee
    pdf.setFillColor(colors.HexColor("#f5f5f5"))
    pdf.setStrokeColor(colors.HexColor("#d0d0d0"))
    pdf.rect(x, y - 44, width, 44, fill=1, stroke=1)

    left = [
        ("Employee No:", employee.employee_number),
        ("Name:", employee.full_name),
        ("Bank:", f"{employee.bank_name} - {employee.bank_branch_name}"),
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
        pdf.setFont("Helvetica-Bold", 6)
        pdf.drawString(x, y, label)
        pdf.setFont("Helvetica", 6)
        pdf.drawString(x + 64, y, _clip(str(value), 38))
        y -= 12


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
