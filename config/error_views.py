"""
Custom error page handlers.

These replace Django's default error pages, which expose framework
information. Templates live in templates/errors/ and are deliberately minimal.
"""

from django.conf import settings
from django.shortcuts import render


def _ctx():
    return {"COMPANY_NAME": getattr(settings, "COMPANY_NAME", "Payroll")}


def handler403(request, exception=None):
    return render(request, "errors/403.html", _ctx(), status=403)


def handler404(request, exception=None):
    return render(request, "errors/404.html", _ctx(), status=404)


def handler500(request):
    return render(request, "errors/500.html", _ctx(), status=500)
