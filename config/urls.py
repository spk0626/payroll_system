"""
Root URL configuration.

The admin is served at a custom URL path (not /admin/) configured via
the ADMIN_URL environment variable. This obscures it from automated scanners.
"""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

admin.site.site_header = f"{settings.COMPANY_NAME} — Payroll Administration"
admin.site.site_title = f"{settings.COMPANY_NAME} Payroll"
admin.site.index_title = "Administration"

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls", namespace="accounts")),
    path("portal/", include("payroll.urls", namespace="payroll")),
]

# Serve media files in development only
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [
            path("__debug__/", include("debug_toolbar.urls")),
        ]
