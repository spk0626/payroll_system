"""
Context processors that inject company-wide settings into every template.

This means templates can use {{ COMPANY_NAME }}, {{ CURRENCY_SYMBOL }} etc.
without the view needing to pass them explicitly every time.
"""

from django.conf import settings


def company_settings(request):
    """Inject company-level settings into every template context."""
    logo_url = ""
    try:
        from core.models import CompanySetting

        setting = CompanySetting.load()
        if setting.logo:
            logo_url = setting.logo.url
    except Exception:
        logo_url = ""

    return {
        "COMPANY_NAME": getattr(settings, "COMPANY_NAME", ""),
        "COMPANY_ADDRESS": getattr(settings, "COMPANY_ADDRESS", ""),
        "CURRENCY_SYMBOL": getattr(settings, "CURRENCY_SYMBOL", "LKR"),
        "COMPANY_LOGO_URL": logo_url,
    }
