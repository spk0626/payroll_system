from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect


class AdminPortalStaffOnlyMiddleware:
    """
    Keep employee and admin portal sessions from bleeding into each other.

    Django uses one auth session per browser. Without this, an employee who opens
    the admin portal sees Django's "authenticated but not authorized" message.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        admin_path = "/" + settings.ADMIN_URL.strip("/") + "/"

        if (
            request.path.startswith(admin_path)
            and request.user.is_authenticated
            and not request.user.is_staff
        ):
            logout(request)
            return redirect(f"{admin_path}login/?next={admin_path}")

        return self.get_response(request)
