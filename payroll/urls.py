"""URL patterns for the employee self-service portal."""

from django.urls import path
from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
]
