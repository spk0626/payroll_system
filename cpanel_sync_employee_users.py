"""
Sync Employee email/name/status to linked Django User accounts.

Run this from cPanel's "Execute python script" field after deploying changes if
employees were edited before user-account syncing was added.
"""

import os
import sys

import django


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.cpanel")


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    django.setup()

    from employees.models import Employee
    from employees.signals import sync_user_account

    synced = 0
    skipped = 0
    failed = 0

    for employee in Employee.objects.select_related("user").all():
        if not employee.user_id:
            skipped += 1
            print("Skipped {0}: no linked user".format(employee.employee_number))
            continue
        if sync_user_account(employee):
            synced += 1
            print("Synced {0}: {1}".format(employee.employee_number, employee.email))
        else:
            failed += 1
            print("Failed {0}: {1}".format(employee.employee_number, employee.email))

    print("Done. Synced: {0}, skipped: {1}, failed: {2}".format(synced, skipped, failed))


if __name__ == "__main__":
    main()
