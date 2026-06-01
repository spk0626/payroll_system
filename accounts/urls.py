"""
URL patterns for the accounts app.

All auth-related routes live here under the empty prefix (root of the site).
The employee portal lives under /portal/ (payroll app).
"""

from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # ── Login / logout ───────────────────────────────────────────────────────
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),

    # ── Password management ──────────────────────────────────────────────────
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("forgot-password/", views.PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
