"""
Context processors that inject company-wide settings into every template.

This means templates can use {{ COMPANY_NAME }}, {{ CURRENCY_SYMBOL }} etc.
without the view needing to pass them explicitly every time.
"""

from django.conf import settings


def company_settings(request):
    """Inject company-level settings into every template context."""
    return {
        "COMPANY_NAME": getattr(settings, "COMPANY_NAME", ""),
        "COMPANY_ADDRESS": getattr(settings, "COMPANY_ADDRESS", ""),
        "CURRENCY_SYMBOL": getattr(settings, "CURRENCY_SYMBOL", "LKR"),
    }
