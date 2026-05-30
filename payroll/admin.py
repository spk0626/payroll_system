"""
Payroll admin — PaySheet, UploadBatch, EmailLog.

PaySheet and UploadBatch are read-mostly in the admin.
The primary write path is through the upload view (D4).
Manual edits to PaySheet JSON are supported for corrections.
"""

from django.contrib import admin
from django.utils.html import format_html, format_html_join

from core.constants import MONTHS, BatchStatus, EmailStatus
from .models import EmailLog, PaySheet, UploadBatch


@admin.register(UploadBatch)
class UploadBatchAdmin(admin.ModelAdmin):
    list_display = [
        "category",
        "month_year_display",
        "status_badge",
        "records_created",
        "records_updated",
        "records_skipped",
        "warning_count",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["status", "category", "year", "month"]
    readonly_fields = [
        "category", "uploaded_by", "month", "year",
        "original_filename", "file_path", "status",
        "records_created", "records_updated", "records_skipped",
        "warnings_formatted", "processing_log", "created_at",
    ]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        # Batches are created by the upload engine, not manually
        return False

    def has_delete_permission(self, request, obj=None):
        # Batches are part of the audit trail — superadmin only
        return request.user.is_superuser

    @admin.display(description="Month / Year")
    def month_year_display(self, obj):
        month_name = dict(MONTHS).get(obj.month, str(obj.month))
        return f"{month_name} {obj.year}"

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            BatchStatus.DONE: "#2e7d32",
            BatchStatus.FAILED: "#c62828",
            BatchStatus.PROCESSING: "#e65100",
            BatchStatus.PENDING: "#757575",
        }
        colour = colours.get(obj.status, "#757575")
        return format_html(
            '<span style="color:{};font-weight:500;">● {}</span>',
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Warnings")
    def warning_count(self, obj):
        count = len(obj.warnings) if obj.warnings else 0
        if count == 0:
            return "—"
        return format_html('<span style="color:#e65100;">⚠ {}</span>', count)

    @admin.display(description="Warnings detail")
    def warnings_formatted(self, obj):
        if not obj.warnings:
            return "No warnings."
        items = format_html_join("", "<li>{}</li>", ((warning,) for warning in obj.warnings))
        return format_html("<ul>{}</ul>", items)


@admin.register(PaySheet)
class PaySheetAdmin(admin.ModelAdmin):
    list_display = [
        "employee",
        "month_year_display",
        "category_snapshot",
        "gross_total_display",
        "updated_at",
    ]
    list_filter = ["year", "month", "category_snapshot"]
    search_fields = ["employee__full_name", "employee__employee_number"]
    readonly_fields = ["id", "employee", "category_snapshot", "upload_batch", "created_at"]
    ordering = ["-year", "-month", "employee__full_name"]
    list_select_related = ["employee", "category_snapshot"]

    fieldsets = [
        (
            "Identity",
            {"fields": ["id", "employee", "category_snapshot", "upload_batch"]},
        ),
        (
            "Salary data",
            {
                "fields": ["month", "year", "breakdown", "gross_total"],
                "description": (
                    "The breakdown field contains the full salary structure as JSON. "
                    "Edit carefully — changes are immediate and affect the employee portal."
                ),
            },
        ),
        (
            "Timestamps",
            {"classes": ["collapse"], "fields": ["created_at", "updated_at"]},
        ),
    ]

    def has_add_permission(self, request):
        # PaySheets are created by the upload engine, not manually
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Month / Year")
    def month_year_display(self, obj):
        return f"{obj.get_month_display_name()} {obj.year}"

    @admin.display(description="Gross total", ordering="gross_total")
    def gross_total_display(self, obj):
        from django.conf import settings
        symbol = getattr(settings, "CURRENCY_SYMBOL", "LKR")
        return f"{symbol} {obj.gross_total:,.2f}"


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = [
        "employee",
        "paysheet_month_year",
        "status_badge",
        "sent_at",
        "error_preview",
    ]
    list_filter = ["status", "batch_sent_at"]
    search_fields = ["employee__full_name", "employee__email"]
    readonly_fields = [
        "paysheet", "employee", "status", "error_message",
        "sent_at", "batch_sent_at",
    ]
    ordering = ["-batch_sent_at"]
    list_select_related = ["employee", "paysheet"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Pay sheet")
    def paysheet_month_year(self, obj):
        return str(obj.paysheet)

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {
            EmailStatus.SENT: "#2e7d32",
            EmailStatus.FAILED: "#c62828",
            EmailStatus.PENDING: "#757575",
        }
        colour = colours.get(obj.status, "#757575")
        return format_html(
            '<span style="color:{};font-weight:500;">● {}</span>',
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Error")
    def error_preview(self, obj):
        if not obj.error_message:
            return "—"
        return obj.error_message[:80] + ("…" if len(obj.error_message) > 80 else "")
