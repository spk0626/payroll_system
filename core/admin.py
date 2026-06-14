from django.contrib import admin

from .models import CompanySetting


@admin.register(CompanySetting)
class CompanySettingAdmin(admin.ModelAdmin):
    fields = ["logo", "updated_at"]
    readonly_fields = ["updated_at"]

    def has_add_permission(self, request):
        return not CompanySetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
