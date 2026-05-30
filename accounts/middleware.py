"""
Custom middleware for the accounts app.

SessionIdleTimeoutMiddleware:
    Logs out users who have been idle for longer than SESSION_IDLE_TIMEOUT seconds.
    Works by recording the last activity timestamp in the session on every request
    and comparing it against the configured timeout on the next request.

ForcePasswordChangeMiddleware:
    Intercepts every request from a user who has must_change_password=True
    and redirects them to the change-password page.
    Exempts: the change-password URL itself, logout, static files, and admin.
"""

import logging
import time

from django.conf import settings
from django.contrib import auth, messages
from django.shortcuts import redirect
from django.urls import resolve, reverse, Resolver404

logger = logging.getLogger(__name__)

# URLs that are always accessible regardless of password-change status.
_FORCE_CHANGE_EXEMPT_URL_NAMES = frozenset([
    "accounts:change_password",
    "accounts:logout",
])


class SessionIdleTimeoutMiddleware:
    """
    Terminate sessions that have been idle for SESSION_IDLE_TIMEOUT seconds.

    The timeout is stored in settings so it can be changed without a deployment.
    The last-activity timestamp is stored in the session (server-side),
    not in a cookie, so it cannot be tampered with by the client.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, "SESSION_IDLE_TIMEOUT", 1800)

    def __call__(self, request):
        if request.user.is_authenticated:
            last_activity = request.session.get("_last_activity")
            now = time.time()

            if last_activity is not None:
                elapsed = now - last_activity
                if elapsed > self.timeout:
                    logger.info(
                        "Session idle timeout for user %s (idle %.0fs).",
                        request.user.username,
                        elapsed,
                    )
                    auth.logout(request)
                    messages.info(
                        request,
                        "Your session expired due to inactivity. Please log in again.",
                    )
                    return redirect(settings.LOGIN_URL)

            # Update last activity on every authenticated request.
            request.session["_last_activity"] = now

        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    """
    Redirect users who must change their password before doing anything else.

    Triggered when Employee.must_change_password is True — set automatically
    on account creation (auto-generated passwords must not remain in use).

    Exempt paths: change-password view, logout, static/media files, and admin.
    Everything else redirects to the change-password page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._needs_redirect(request):
            return redirect("accounts:change_password")
        return self.get_response(request)

    def _needs_redirect(self, request) -> bool:
        if not request.user.is_authenticated:
            return False

        # Admin users are not employees; skip this check entirely.
        if request.user.is_staff or request.user.is_superuser:
            return False

        # Check the Employee profile flag.
        employee = getattr(request.user, "employee", None)
        if employee is None or not employee.must_change_password:
            return False

        # Allow exempt URLs through.
        path = request.path_info
        if path.startswith(("/static/", "/media/", f"/{settings.ADMIN_URL}")):
            return False

        try:
            url_name = resolve(path).view_name
            if url_name in _FORCE_CHANGE_EXEMPT_URL_NAMES:
                return False
        except Resolver404:
            return False

        return True