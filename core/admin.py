from django.contrib import admin
from django.shortcuts import redirect
from django.utils.html import format_html

from .admin_mixins import ActionLabelMixin
from .models import CompanySetting


@admin.register(CompanySetting)
class CompanySettingAdmin(ActionLabelMixin, admin.ModelAdmin):
    fields = ["company_name", "logo", "logo_preview", "updated_at"]
    readonly_fields = ["logo_preview", "updated_at"]

    def logo_preview(self, obj):
        if not obj or not obj.logo:
            return "No logo uploaded."
        return format_html(
            '<div style="display:flex;align-items:center;gap:12px;">'
            '<span style="width:72px;height:72px;display:grid;place-items:center;'
            'border:1px solid #D8E1F0;background:#0243B0;padding:8px;">'
            '<img src="{}" style="max-width:100%;max-height:100%;object-fit:contain;" alt="">'
            "</span>"
            "<span>Current uploaded logo</span>"
            "</div>",
            obj.logo.url,
        )

    logo_preview.short_description = "Logo preview"

    def changelist_view(self, request, extra_context=None):
        setting = CompanySetting.objects.first()
        if setting:
            return redirect("admin:core_companysetting_change", setting.pk)
        return super().changelist_view(request, extra_context)

    def has_add_permission(self, request):
        return not CompanySetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
