"""
Seed default demo users without shell access.

Upload this file to the application root and run `cpanel_seed_default_users.py`
from cPanel's "Execute python script" field after migrations have completed.
"""

import os
import sys

from django.core.management import execute_from_command_line


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cpanel")


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    execute_from_command_line([
        "manage.py",
        "seed_default_users",
        "--settings=config.settings.cpanel",
    ])
