"""
Seed the default admin portal user.

This command is intentionally small and idempotent for deployment smoke tests.
Rotate these passwords after handover before storing real payroll data.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "SyntaxAdmin#2026!"


class Command(BaseCommand):
    help = "Create or reset the default admin portal user."

    def handle(self, *args, **options):
        admin_user, _ = User.objects.update_or_create(
            username=ADMIN_USERNAME,
            defaults={
                "email": ADMIN_EMAIL,
                "first_name": "System",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        admin_user.set_password(ADMIN_PASSWORD)
        admin_user.save()

        self.stdout.write(self.style.SUCCESS("Default admin user seeded."))
