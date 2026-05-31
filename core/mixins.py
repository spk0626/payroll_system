"""
Reusable mixins for views and admin classes.
"""

from django.contrib import auth, messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


class EmployeeRequiredMixin(LoginRequiredMixin):
    """
    Ensures the requesting user has an associated Employee profile.

    Used on all employee portal views. Redirects unauthenticated users
    to the login page. Raises 403 if authenticated but not an employee
    (e.g. admin users accidentally hitting a portal URL).
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not hasattr(request.user, "employee"):
            auth.logout(request)
            messages.info(request, "Please sign in with an employee account to view the payslip portal.")
            return redirect("accounts:login")
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(LoginRequiredMixin):
    """
    Ensures the requesting user is a staff or superuser.
    Used on any non-admin views that require staff access.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            raise PermissionDenied("Staff access required.")
        return super().dispatch(request, *args, **kwargs)
