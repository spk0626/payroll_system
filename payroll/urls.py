from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("payslip/<uuid:uuid>/", views.PayslipDetailView.as_view(), name="payslip_detail"),
    path("payslip/<uuid:uuid>/print/", views.PayslipPrintView.as_view(), name="payslip_print"),
]
