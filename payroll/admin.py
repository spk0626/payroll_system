"""
Payroll admin - PaySheet, UploadBatch, EmailLog, CategoryParserConfig.

This file owns the admin-side payroll interface:
- CategoryParserConfig: set up once per category, editable inline
- UploadBatch: read-only audit log with warning display and email send action
- PaySheet: inspectable and manually editable for corrections
- EmailLog: full send history with retry action
"""

import logging

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from core.constants import MONTHS, BatchStatus, EmailStatus
from .models import CategoryParserConfig, EmailLog, PaySheet, UploadBatch

logger = logging.getLogger(__name__)


@admin.register(CategoryParserConfig)
class CategoryParserConfigAdmin(admin.ModelAdmin):
    """
    Parser configuration for Excel salary sheets.

    Set once per category. Controls which row contains employee numbers
    and which rows are informational, not salary components.
    """

    list_display = [
        "category",
        "emp_id_row_label",
        "fixed_labels_preview",
        "updated_at",
    ]
    search_fields = ["category__name", "emp_id_row_label"]
    ordering = ["category__name"]

    fieldsets = [
        (
            None,
            {
                "fields": ["category", "emp_id_row_label", "fixed_info_row_labels", "notes"],
                "description": (
                    "<strong>Employee ID row label</strong>: the exact text in column A "
                    "that identifies the row containing employee numbers. "
                    "Case-insensitive. Example: <code>Employee</code>, <code>Staff ID</code>.<br><br>"
                    "<strong>Fixed info row labels</strong>: JSON list of rows to skip - "
                    "informational rows that are NOT salary components. "
                    'Example: <code>["Employee Name", "Designation", "Department"]</code><br><br>'
                    "Everything else in column A will be treated as a salary component."
                ),
            },
        ),
    ]

    @admin.display(description="Fixed info rows")
    def fixed_labels_preview(self, obj):
        labels = obj.fixed_info_row_labels or []
        if not labels:
            return format_html('<span style="color:#aaa;">None configured</span>')
        preview = ", ".join(str(label) for label in labels[:4])
        if len(labels) > 4:
            preview += f" (+{len(labels) - 4} more)"
        return preview


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
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
class PaySheetAdmin(admin.ModelAdmin):
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
    readonly_fields = ["id", "employee", "category_snapshot", "upload_batch", "created_at"]
    ordering = ["-year", "-month", "employee__full_name"]
    list_select_related = ["employee", "category_snapshot"]
    list_per_page = 50

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
                "fields": ["month", "year", "breakdown", "gross_total"],
                "description": (
                    "<strong>Edit carefully.</strong> The <code>breakdown</code> "
                    "field is raw JSON. Format: "
                    '<code>{"Component Name": "50000.00", ...}</code>. '
                    "Changes take effect immediately in the employee portal. "
                    "Prefer re-uploading a corrected Excel file where possible."
                ),
            },
        ),
        (
            "Timestamps",
            {"classes": ["collapse"], "fields": ["created_at", "updated_at"]},
        ),
    ]

    def has_add_permission(self, request):
        return False

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
class EmailLogAdmin(admin.ModelAdmin):
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
