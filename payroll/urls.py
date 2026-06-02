from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("payslips/print/", views.PayslipPrintAllView.as_view(), name="payslip_print_all"),
    path("payslips/download/", views.PayslipDownloadAllView.as_view(), name="payslip_download_all"),
    path("payslip/<uuid:uuid>/", views.PayslipDetailView.as_view(), name="payslip_detail"),
    path("payslip/<uuid:uuid>/print/", views.PayslipPrintView.as_view(), name="payslip_print"),
]
