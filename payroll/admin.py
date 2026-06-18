"""
Payroll admin - PaySheet, UploadBatch, EmailLog.

This file owns the admin-side payroll interface:
- UploadBatch: read-only audit log with warning display and email send action
- PaySheet: inspectable and manually editable for corrections
- EmailLog: full send history with retry action
"""

import logging
import csv
from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from core.admin_mixins import ActionLabelMixin
from core.constants import MONTHS, BatchStatus, EmailStatus
from core.validators import validate_excel_file
from employees.models import Employee, EmployeeCategory
from .models import EmailLog, PaySheet, UploadBatch

logger = logging.getLogger(__name__)


class SalaryUploadForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=EmployeeCategory.objects.order_by("name"),
        empty_label="Select a category...",
        help_text="Only active employees in this category will be matched.",
    )
    month = forms.ChoiceField(choices=MONTHS)
    year = forms.IntegerField(min_value=2000, max_value=2100)
    salary_file = forms.FileField(
        help_text="Upload a .xlsx file. Row 1 must contain employee numbers from column B onward. Column A contains payroll labels."
    )

    def clean_salary_file(self):
        salary_file = self.cleaned_data["salary_file"]
        validate_excel_file(salary_file)
        return salary_file


class BreakdownTableWidget(forms.Widget):
    template_name = None

    def render(self, name, value, attrs=None, renderer=None):
        value = value or {}
        if not isinstance(value, dict):
            value = {}
        rows = []
        for label, amount in value.items():
            rows.append(
                format_html(
                    '<tr><td><input type="text" name="breakdown_label" value="{}"></td>'
                    '<td><input type="text" name="breakdown_amount" value="{}"></td></tr>',
                    label,
                    amount,
                )
            )
        for _ in range(5):
            rows.append(
                format_html(
                    '<tr class="breakdown-editor__new-row">'
                    '<td><input type="text" name="breakdown_label" value="" '
                    'placeholder="Add salary row label"></td>'
                    '<td><input type="text" name="breakdown_amount" value="" '
                    'placeholder="0.00"></td></tr>'
                )
            )
        return format_html(
            '<table class="breakdown-editor"><thead><tr><th>Description</th>'
            '<th>Amount</th></tr></thead><tbody>{}</tbody></table>'
            '<p class="help">Edit existing rows or use the blank rows at the end '
            'to add new salary rows. Leave unused labels blank.</p>',
            format_html_join("", "{}", ((row,) for row in rows)),
        )

    def value_from_datadict(self, data, files, name):
        labels = data.getlist("breakdown_label")
        amounts = data.getlist("breakdown_amount")
        breakdown = {}
        for label, amount in zip(labels, amounts):
            label = label.strip()
            amount = amount.strip()
            if not label:
                continue
            breakdown[label] = amount or "0"
        return breakdown


class PaySheetAdminForm(forms.ModelForm):
    breakdown_editor = forms.Field(
        label="Salary rows",
        required=False,
        widget=BreakdownTableWidget,
    )

    class Meta:
        model = PaySheet
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["breakdown_editor"].initial = self.instance.breakdown or {}

    def clean_breakdown_editor(self):
        breakdown = self.cleaned_data["breakdown_editor"]
        cleaned = {}
        total = Decimal("0")
        for label, amount in breakdown.items():
            try:
                amount_dec = Decimal(str(amount).replace(",", ""))
            except InvalidOperation:
                raise forms.ValidationError(f"'{label}' amount must be a number.")
            cleaned[label] = str(amount_dec)
            total += amount_dec
        self.cleaned_data["_gross_total"] = total
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.breakdown = self.cleaned_data["breakdown_editor"]
        obj.gross_total = self.cleaned_data["_gross_total"]
        if commit:
            obj.save()
            self.save_m2m()
        return obj


@admin.register(UploadBatch)
class UploadBatchAdmin(ActionLabelMixin, admin.ModelAdmin):
    """
    Audit log for every Excel salary upload.

    Read-only except for superadmin delete. Every upload, including failed
    ones, creates a batch record so salary data has a complete audit trail.
    """

    list_display = [
        "month_year_display",
        "category",
        "status_badge",
        "records_created",
        "records_updated",
        "records_skipped",
        "warning_count",
        "uploaded_by",
        "created_at",
        "email_action_link",
    ]
    list_filter = ["status", "category", "year", "month"]
    search_fields = ["category__name", "uploaded_by__username", "original_filename"]
    readonly_fields = [
        "category",
        "uploaded_by",
        "month",
        "year",
        "original_filename",
        "file_path",
        "status",
        "records_created",
        "records_updated",
        "records_skipped",
        "warnings_formatted",
        "processing_log",
        "created_at",
    ]
    ordering = ["-created_at"]
    actions = ["send_payslip_emails", "retry_failed_emails_action"]
    change_list_template = "admin/payroll/uploadbatch/change_list.html"

    fieldsets = [
        (
            "Upload details",
            {
                "fields": [
                    "category",
                    "uploaded_by",
                    "month",
                    "year",
                    "original_filename",
                    "status",
                    "created_at",
                ],
            },
        ),
        (
            "Processing results",
            {
                "fields": [
                    "records_created",
                    "records_updated",
                    "records_skipped",
                    "warnings_formatted",
                    "processing_log",
                ],
            },
        ),
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "upload-salary-sheet/",
                self.admin_site.admin_view(self.upload_salary_sheet),
                name="payroll_uploadbatch_upload",
            ),
            path(
                "<int:batch_id>/download-csv/",
                self.admin_site.admin_view(self.download_csv),
                name="payroll_uploadbatch_download_csv",
            ),
            path(
                "<int:batch_id>/download-excel/",
                self.admin_site.admin_view(self.download_excel),
                name="payroll_uploadbatch_download_excel",
            ),
            path(
                "<int:batch_id>/commit-preview/",
                self.admin_site.admin_view(self.commit_preview),
                name="payroll_uploadbatch_commit_preview",
            ),
        ]
        return custom_urls + urls

    def _preview_rows(self, diff):
        labels = []
        rows = []
        entries = [*diff.to_create, *diff.to_update]
        for entry in entries:
            for label in (entry.breakdown or {}).keys():
                if label not in labels:
                    labels.append(label)
        for index, entry in enumerate(entries):
            rows.append({
                "index": index,
                "employee": entry.employee,
                "action": entry.action,
                "existing_id": entry.existing_paysheet.pk if entry.existing_paysheet else "",
                "breakdown": entry.breakdown or {},
                "cells": [
                    {"label": label, "value": (entry.breakdown or {}).get(label, "0")}
                    for label in labels
                ],
            })
        return rows, labels

    def upload_salary_sheet(self, request):
        """
        Upload, parse, and commit one monthly salary sheet from the admin.

        Employee numbers are read from row 1; column A labels become payroll rows.
        """
        if request.method == "POST":
            form = SalaryUploadForm(request.POST, request.FILES)
            if form.is_valid():
                category = form.cleaned_data["category"]
                month = int(form.cleaned_data["month"])
                year = form.cleaned_data["year"]
                salary_file = form.cleaned_data["salary_file"]

                from payroll.services.upload_service import (
                    build_diff,
                    commit_diff,
                    save_upload_file,
                )

                abs_path, batch = save_upload_file(
                    salary_file,
                    category=category,
                    month=month,
                    year=year,
                    user=request.user,
                )
                diff = build_diff(abs_path, category, month=month, year=year, batch=batch)

                if diff.has_fatal_errors:
                    self.message_user(
                        request,
                        "Upload failed: " + " ".join(diff.errors),
                        messages.ERROR,
                    )
                    return redirect("admin:payroll_uploadbatch_change", batch.pk)

                rows, labels = self._preview_rows(diff)
                return render(
                    request,
                    "admin/payroll/uploadbatch/preview.html",
                    {
                        **self.admin_site.each_context(request),
                        "opts": self.model._meta,
                        "title": "Review salary upload",
                        "batch": batch,
                        "rows": rows,
                        "labels": labels,
                        "warnings": diff.warnings,
                        "absent": diff.absent,
                    },
                )
        else:
            form = SalaryUploadForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Upload salary sheet",
            "form": form,
        }
        return render(request, "admin/payroll/uploadbatch/upload.html", context)

    def commit_preview(self, request, batch_id):
        if request.method != "POST":
            return redirect("admin:payroll_uploadbatch_change", batch_id)

        from payroll.services.upload_service import DiffEntry, DiffResult, commit_diff

        batch = get_object_or_404(UploadBatch, pk=batch_id)
        labels = request.POST.getlist("label")
        row_count = int(request.POST.get("row_count", "0") or 0)
        diff = DiffResult(batch_id=batch.pk)

        for row_index in range(row_count):
            employee_id = request.POST.get(f"employee_{row_index}")
            action = request.POST.get(f"action_{row_index}")
            if not employee_id or action not in {"create", "update"}:
                continue
            employee = get_object_or_404(Employee, pk=employee_id)
            breakdown = {}
            gross_total = Decimal("0")
            for label_index, label in enumerate(labels):
                raw_amount = request.POST.get(f"amount_{row_index}_{label_index}", "0").replace(",", "").strip() or "0"
                try:
                    amount = Decimal(raw_amount)
                except InvalidOperation:
                    self.message_user(
                        request,
                        f"{employee.employee_number} / {label}: amount must be a number.",
                        messages.ERROR,
                    )
                    return redirect("admin:payroll_uploadbatch_change", batch.pk)
                breakdown[label] = str(amount)
                gross_total += amount

            existing_paysheet = None
            existing_id = request.POST.get(f"existing_{row_index}")
            if existing_id:
                existing_paysheet = PaySheet.objects.get(pk=existing_id)

            entry = DiffEntry(
                employee=employee,
                action=action,
                breakdown=breakdown,
                gross_total=gross_total,
                existing_paysheet=existing_paysheet,
            )
            if action == "create":
                diff.to_create.append(entry)
            else:
                diff.to_update.append(entry)

        batch = commit_diff(
            diff,
            remove_absent_ids=[],
            category=batch.category,
            month=batch.month,
            year=batch.year,
        )
        self.message_user(
            request,
            f"Salary upload saved. Created: {batch.records_created}. Updated: {batch.records_updated}.",
            messages.SUCCESS,
        )
        paysheets = (
            PaySheet.objects
            .filter(upload_batch=batch)
            .select_related("employee", "category_snapshot")
            .order_by("employee__employee_number")
        )
        return render(
            request,
            "admin/payroll/uploadbatch/result.html",
            {
                **self.admin_site.each_context(request),
                "opts": self.model._meta,
                "title": "Salary upload results",
                "batch": batch,
                "paysheets": paysheets,
                "warnings": batch.warnings,
            },
        )

    def download_csv(self, request, batch_id):
        batch = UploadBatch.objects.get(pk=batch_id)
        paysheets, labels = self._batch_export_data(batch)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="paysheets-{batch.year}-{batch.month:02d}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(self._export_headers(labels))
        for paysheet in paysheets:
            writer.writerow(self._export_row(paysheet, labels))
        return response

    def download_excel(self, request, batch_id):
        from openpyxl import Workbook

        batch = UploadBatch.objects.get(pk=batch_id)
        paysheets, labels = self._batch_export_data(batch)
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Paysheets"
        sheet.append(self._export_headers(labels))
        for paysheet in paysheets:
            sheet.append(self._export_row(paysheet, labels))

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = (
            f'attachment; filename="paysheets-{batch.year}-{batch.month:02d}.xlsx"'
        )
        workbook.save(response)
        return response

    def _batch_export_data(self, batch):
        paysheets = (
            PaySheet.objects
            .filter(upload_batch=batch)
            .select_related("employee", "category_snapshot")
            .order_by("employee__employee_number")
        )
        labels = []
        for paysheet in paysheets:
            for label in paysheet.breakdown.keys():
                if label not in labels:
                    labels.append(label)
        return paysheets, labels

    def _export_headers(self, labels):
        return [
            "Employee number",
            "Employee name",
            "Month",
            "Year",
            *labels,
            "Gross total",
        ]

    def _export_row(self, paysheet, labels):
        return [
            paysheet.employee.employee_number,
            paysheet.employee.full_name,
            paysheet.get_month_display_name(),
            paysheet.year,
            *[paysheet.breakdown.get(label, "") for label in labels],
            paysheet.gross_total,
        ]

    @admin.action(description="Send payslip notification emails for selected batches")
    def send_payslip_emails(self, request, queryset):
        """
        Trigger bulk payslip email sends for selected completed upload batches.
        """
        from payroll.services.email_service import send_payslip_notifications

        total_sent = 0
        total_failed = 0
        batch_sent_at = timezone.now()

        for batch in queryset.filter(status=BatchStatus.DONE):
            paysheets = list(
                PaySheet.objects
                .filter(upload_batch=batch)
                .select_related("employee", "employee__user", "category_snapshot")
            )

            if not paysheets:
                self.message_user(
                    request,
                    f"Batch '{batch}': no paysheets found.",
                    messages.WARNING,
                )
                continue

            result = send_payslip_notifications(paysheets, batch_sent_at=batch_sent_at)
            total_sent += result["sent"]
            total_failed += result["failed"]

            logger.info(
                "Admin %s triggered email send for batch %s: %d sent, %d failed.",
                request.user.username,
                batch.pk,
                result["sent"],
                result["failed"],
            )

        if total_failed > 0:
            self.message_user(
                request,
                f"Emails sent: {total_sent}. Failed: {total_failed}. "
                "Check Email logs and filter by Status = Failed to retry.",
                messages.WARNING,
            )
        else:
            self.message_user(
                request,
                f"All {total_sent} payslip emails sent successfully.",
                messages.SUCCESS,
            )

    @admin.action(description="Retry failed emails for selected batches")
    def retry_failed_emails_action(self, request, queryset):
        """Re-send only failed emails linked to the selected upload batches."""
        from payroll.services.email_service import send_payslip_notifications

        total_sent = 0
        total_failed = 0

        for batch in queryset.filter(status=BatchStatus.DONE):
            failed_logs = EmailLog.objects.filter(
                paysheet__upload_batch=batch,
                status=EmailStatus.FAILED,
            ).select_related(
                "paysheet",
                "paysheet__employee",
                "paysheet__category_snapshot",
                "employee",
            )
            result = send_payslip_notifications(
                [log.paysheet for log in failed_logs],
                batch_sent_at=timezone.now(),
            )
            total_sent += result["sent"]
            total_failed += result["failed"]

        self.message_user(
            request,
            f"Retry complete. Sent: {total_sent}. Still failing: {total_failed}.",
            messages.SUCCESS if total_failed == 0 else messages.WARNING,
        )

    @admin.display(description="Period", ordering="-year")
    def month_year_display(self, obj):
        month_name = dict(MONTHS).get(obj.month, str(obj.month))
        return f"{month_name} {obj.year}"

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            BatchStatus.DONE: ("#e8f5e9", "#2e7d32"),
            BatchStatus.FAILED: ("#fce4e4", "#c62828"),
            BatchStatus.PROCESSING: ("#fff8e1", "#e65100"),
            BatchStatus.PENDING: ("#f5f5f5", "#757575"),
        }
        bg, fg = colours.get(obj.status, ("#f5f5f5", "#757575"))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:4px;'
            'font-size:12px;font-weight:600;">{}</span>',
            bg,
            fg,
            obj.get_status_display(),
        )

    @admin.display(description="Warnings")
    def warning_count(self, obj):
        count = len(obj.warnings) if obj.warnings else 0
        if count == 0:
            return format_html('<span style="color:#aaa;">{}</span>', "-")
        return format_html(
            '<span style="color:#e65100;font-weight:600;">{} warning(s)</span>',
            count,
        )

    @admin.display(description="Email")
    def email_action_link(self, obj):
        if obj.status != BatchStatus.DONE:
            return format_html('<span style="color:#aaa;">-</span>')
        paysheet_count = obj.paysheets.count()
        sent_count = EmailLog.objects.filter(
            paysheet__upload_batch=obj,
            status=EmailStatus.SENT,
        ).count()
        if sent_count == paysheet_count and paysheet_count > 0:
            return format_html(
                '<span style="color:#2e7d32;font-size:12px;">{}</span>',
                "All sent",
            )
        return format_html(
            '<span style="color:#555;font-size:12px;">{}/{} sent</span>',
            sent_count,
            paysheet_count,
        )

    @admin.display(description="Warnings detail")
    def warnings_formatted(self, obj):
        if not obj.warnings:
            return "No warnings."
        items = format_html_join(
            "",
            '<li style="margin-bottom:4px">{}</li>',
            ((warning,) for warning in obj.warnings),
        )
        return format_html('<ul style="margin:0;padding-left:1.25rem">{}</ul>', items)


@admin.register(PaySheet)
class PaySheetAdmin(ActionLabelMixin, admin.ModelAdmin):
    """
    Salary breakdown records.

    Read-mostly. Manual editing is supported for corrections, but corrections
    are better made by re-uploading a corrected Excel file.
    """

    list_display = [
        "employee",
        "month_year_display",
        "category_snapshot",
        "gross_total_display",
        "updated_at",
        "email_status",
    ]
    list_filter = ["year", "month", "category_snapshot"]
    search_fields = [
        "employee__full_name",
        "employee__employee_number",
        "employee__email",
    ]
    readonly_fields = [
        "id",
        "employee",
        "category_snapshot",
        "upload_batch",
        "gross_total",
        "created_at",
        "updated_at",
    ]
    ordering = ["-year", "-month", "employee__full_name"]
    list_select_related = ["employee", "category_snapshot"]
    list_per_page = 50
    form = PaySheetAdminForm

    fieldsets = [
        (
            "Identity",
            {
                "fields": ["id", "employee", "category_snapshot", "upload_batch"],
                "description": "These fields are set at upload time and cannot be changed.",
            },
        ),
        (
            "Salary data",
            {
                "fields": ["month", "year", "breakdown_editor", "gross_total"],
                "description": (
                    "Edit payroll rows carefully. Changes take effect immediately "
                    "in the employee portal."
                ),
            },
        ),
        (
            "Timestamps",
            {"classes": ["collapse"], "fields": ["created_at", "updated_at"]},
        ),
    ]

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ["id", "gross_total", "created_at", "updated_at"]
        return self.readonly_fields

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [
                (
                    "Identity",
                    {
                        "fields": ["employee", "category_snapshot"],
                        "description": "Choose the employee and category for this manual paysheet.",
                    },
                ),
                (
                    "Salary data",
                    {
                        "fields": ["month", "year", "breakdown_editor", "gross_total"],
                        "description": "Gross total is calculated from the salary rows when saved.",
                    },
                ),
            ]
        return self.fieldsets

    def has_add_permission(self, request):
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Period")
    def month_year_display(self, obj):
        return f"{obj.get_month_display_name()} {obj.year}"

    @admin.display(description="Gross total", ordering="gross_total")
    def gross_total_display(self, obj):
        from django.conf import settings
        symbol = getattr(settings, "CURRENCY_SYMBOL", "LKR")
        return f"{symbol} {obj.gross_total:,.2f}"

    @admin.display(description="Email")
    def email_status(self, obj):
        log = obj.email_logs.order_by("-sent_at").first()
        if not log:
            return format_html('<span style="color:#aaa;font-size:12px;">Not sent</span>')
        colour = {
            EmailStatus.SENT: "#2e7d32",
            EmailStatus.FAILED: "#c62828",
            EmailStatus.PENDING: "#888",
        }.get(log.status, "#888")
        return format_html(
            '<span style="color:{};font-size:12px;font-weight:600;">{}</span>',
            colour,
            log.get_status_display(),
        )


@admin.register(EmailLog)
class EmailLogAdmin(ActionLabelMixin, admin.ModelAdmin):
    """
    Full history of every payslip email send attempt.

    Use the retry action to re-send to failed recipients only.
    """

    list_display = [
        "employee",
        "paysheet_period",
        "status_badge",
        "sent_at",
        "error_preview",
    ]
    list_filter = ["status", "batch_sent_at"]
    search_fields = ["employee__full_name", "employee__email", "employee__employee_number"]
    readonly_fields = [
        "paysheet",
        "employee",
        "status",
        "error_message",
        "sent_at",
        "batch_sent_at",
    ]
    ordering = ["-batch_sent_at", "employee__full_name"]
    list_select_related = ["employee", "paysheet"]
    list_per_page = 100
    actions = ["retry_selected_emails"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.action(description="Retry sending selected failed emails")
    def retry_selected_emails(self, request, queryset):
        """Retry only the selected EmailLog entries that have status=failed."""
        from payroll.services.email_service import send_payslip_notifications

        failed_logs = queryset.filter(status=EmailStatus.FAILED).select_related(
            "paysheet",
            "paysheet__employee",
            "paysheet__category_snapshot",
            "employee",
        )

        if not failed_logs.exists():
            self.message_user(request, "No failed emails in selection.", messages.WARNING)
            return

        paysheets = [log.paysheet for log in failed_logs]
        result = send_payslip_notifications(paysheets, batch_sent_at=timezone.now())

        self.message_user(
            request,
            f"Retry complete. Sent: {result['sent']}. Still failing: {result['failed']}.",
            messages.SUCCESS if result["failed"] == 0 else messages.WARNING,
        )

    @admin.display(description="Payslip")
    def paysheet_period(self, obj):
        return str(obj.paysheet)

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            EmailStatus.SENT: ("#e8f5e9", "#2e7d32"),
            EmailStatus.FAILED: ("#fce4e4", "#c62828"),
            EmailStatus.PENDING: ("#f5f5f5", "#757575"),
        }
        bg, fg = colours.get(obj.status, ("#f5f5f5", "#757575"))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:4px;'
            'font-size:12px;font-weight:600;">{}</span>',
            bg,
            fg,
            obj.get_status_display(),
        )

    @admin.display(description="Error")
    def error_preview(self, obj):
        if not obj.error_message:
            return format_html('<span style="color:#aaa;">{}</span>', "-")
        preview = obj.error_message[:100]
        if len(obj.error_message) > 100:
            preview += "..."
        return format_html(
            '<span style="color:#c62828;font-size:12px;">{}</span>',
            preview,
        )
