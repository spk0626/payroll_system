"""URL patterns for the employee self-service portal."""

from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("payslip/<uuid:paysheet_id>/", views.payslip_detail, name="payslip_detail"),
    path("payslip/<uuid:paysheet_id>/print/", views.payslip_print, name="payslip_print"),
]
