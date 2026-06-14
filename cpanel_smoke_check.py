"""
Print basic cPanel runtime checks without shell access.

Run this from cPanel's "Execute python script" field to confirm the deployed
Python app is loading the expected Django settings and URL routes.
"""

import os
import sys

import django
from django.urls import reverse


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cpanel")


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    django.setup()

    from django.conf import settings

    print("Django settings:", os.environ.get("DJANGO_SETTINGS_MODULE"))
    print("Root URLConf:", settings.ROOT_URLCONF)
    print("Allowed hosts:", settings.ALLOWED_HOSTS)
    print("Login URL:", reverse("accounts:login"))
    print("Portal URL:", reverse("payroll:dashboard"))
    print("Admin URL:", "/" + settings.ADMIN_URL)
    print("Smoke check completed.")


if __name__ == "__main__":
    main()
