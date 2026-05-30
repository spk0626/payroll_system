from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import PaySheet


@login_required
def dashboard(request):
    employee = getattr(request.user, "employee", None)
    paysheets = (
        PaySheet.objects.filter(employee=employee)
        .select_related("employee", "category_snapshot")
        .order_by("-year", "-month")
        if employee
        else PaySheet.objects.none()
    )
    return render(
        request,
        "payroll/dashboard.html",
        {
            "employee": employee,
            "entries": paysheets,
        },
    )


@login_required
def payslip_detail(request, paysheet_id):
    paysheet = get_object_or_404(
        PaySheet.objects.select_related("employee", "category_snapshot"),
        pk=paysheet_id,
        employee__user=request.user,
    )
    return render(request, "payroll/payslip_detail.html", {"paysheet": paysheet})


@login_required
def payslip_print(request, paysheet_id):
    paysheet = get_object_or_404(
        PaySheet.objects.select_related("employee", "category_snapshot"),
        pk=paysheet_id,
        employee__user=request.user,
    )
    return render(request, "payroll/payslip_print.html", {"paysheet": paysheet})
