"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if not settings_module or settings_module == "config.settings.development":
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.vercel"

application = get_wsgi_application()
app = application
