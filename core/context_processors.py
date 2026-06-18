"""
Context processors that inject company-wide settings into every template.

This means templates can use {{ COMPANY_NAME }}, {{ CURRENCY_SYMBOL }} etc.
without the view needing to pass them explicitly every time.
"""

from django.conf import settings


DEFAULT_LOGO_URL = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E"
    "%3Crect width='512' height='512' rx='34' fill='%232448ad'/%3E"
    "%3Cpath d='M58 224c34-83 122-151 246-170 31-5 58-5 82-1-64 6-134 28-202 67-65 37-111 81-126 104z' fill='white'/%3E"
    "%3Cpath d='M57 320c8-88 137-184 288-216 63-13 117-8 153 12-72-2-159 20-241 63-98 51-169 111-200 141z' fill='white'/%3E"
    "%3Cpath d='M92 406c6-78 117-151 259-169 54-7 102-1 136 16-68 2-144 21-210 53-84 41-143 80-185 100z' fill='white'/%3E"
    "%3Cpath d='M174 457c18-53 93-96 189-105 42-4 79 0 109 13-45 2-100 17-147 40-57 27-98 49-151 52z' fill='white'/%3E"
    "%3C/svg%3E"
)


def company_settings(request):
    """Inject company-level settings into every template context."""
    company_name = getattr(settings, "COMPANY_NAME", "Syntax Asia")
    logo_url = DEFAULT_LOGO_URL
    context = {
        "COMPANY_ADDRESS": getattr(settings, "COMPANY_ADDRESS", ""),
        "CURRENCY_SYMBOL": getattr(settings, "CURRENCY_SYMBOL", "LKR"),
    }

    try:
        from .models import CompanySetting

        setting = CompanySetting.load()
        company_name = setting.company_name or company_name
        if setting.logo:
            logo_url = setting.logo.url
    except Exception:
        pass

    context.update({
        "COMPANY_NAME": company_name,
        "COMPANY_LOGO_URL": logo_url,
    })

    admin_url = "/" + getattr(settings, "ADMIN_URL", "management-portal/").strip("/")
    if request.path.rstrip("/") == admin_url:
        try:
            from core.constants import MONTHS
            from employees.models import Employee
            from payroll.models import UploadBatch

            last_batch = UploadBatch.objects.order_by("-created_at").first()
            context["employee_count"] = Employee.objects.filter(is_active=True).count()
            if last_batch:
                context["last_batch_month"] = dict(MONTHS).get(last_batch.month, str(last_batch.month))
                context["last_batch_status"] = last_batch.get_status_display()
        except Exception:
            pass

    return context
