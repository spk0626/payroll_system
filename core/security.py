"""
Security utilities and middleware.

SecurityHeadersMiddleware adds CSP and additional security headers not covered
by Django's SecurityMiddleware. It is applied to every response.

The Nginx config handles HSTS and X-Frame-Options at the proxy layer in
production; this middleware adds them for environments where Nginx is not
present, such as local development and CI.
"""

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add HTTP security headers to every response.

    Headers set here:
    - Content-Security-Policy: restricts resource loading
    - Permissions-Policy: disables browser features not needed
    - X-Content-Type-Options: prevents MIME sniffing
    - X-Frame-Options: prevents clickjacking
    - Referrer-Policy: limits referrer leakage
    - Strict-Transport-Security: production HTTPS fallback
    """

    def process_response(self, request, response):
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response["Content-Security-Policy"] = "; ".join(csp_directives)

        response["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), "
            "payment=(), usb=(), bluetooth=()"
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        hsts_seconds = getattr(settings, "SECURE_HSTS_SECONDS", 0)
        if hsts_seconds:
            hsts_value = f"max-age={hsts_seconds}"
            if getattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS", False):
                hsts_value += "; includeSubDomains"
            if getattr(settings, "SECURE_HSTS_PRELOAD", False):
                hsts_value += "; preload"
            response.setdefault("Strict-Transport-Security", hsts_value)

        return response
