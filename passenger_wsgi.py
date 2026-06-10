"""
cPanel Passenger WSGI entrypoint.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cpanel")

from config.wsgi import application  # noqa: E402,F401
