from django.contrib.auth.models import User
from django.core.management import call_command


def test_seed_default_users_is_idempotent(db):
    call_command("seed_default_users")
    call_command("seed_default_users")

    admin = User.objects.get(username="admin")
    assert admin.email == "admin@example.com"
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.check_password("SyntaxAdmin#2026!")
