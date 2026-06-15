"""
cPanel Passenger WSGI entrypoint.
"""

import os
import sys

INTERP = "/home/syntumfz/virtualenv/pay.syntaxasia.digital/3.6/bin/python"

if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

PROJECT_ROOT = os.path.dirname(__file__)
SITE_PACKAGES = "/home/syntumfz/virtualenv/pay.syntaxasia.digital/3.6/lib/python3.6/site-packages"

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SITE_PACKAGES)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cpanel")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
