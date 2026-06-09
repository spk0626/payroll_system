"""
Run cPanel deployment setup commands without shell access.

cPanel's Python App UI can execute Python scripts but may not provide Terminal.
Upload this file to the application root and run `cpanel_setup.py` from the
"Execute python script" field after pip install succeeds.
"""

import os
import sys

from django.core.management import execute_from_command_line


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cpanel")


COMMANDS = [
    ["manage.py", "migrate", "--settings=config.settings.cpanel"],
    ["manage.py", "collectstatic", "--noinput", "--settings=config.settings.cpanel"],
    ["manage.py", "check", "--deploy", "--settings=config.settings.cpanel"],
]


def main():
    for command in COMMANDS:
        print("\nRunning: {0}".format(" ".join(command)))
        execute_from_command_line(command)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
