# Generated manually for admin-account proxy.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdminAccount",
            fields=[],
            options={
                "verbose_name": "Admin account",
                "verbose_name_plural": "Admin accounts",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("auth.user",),
            managers=[],
        ),
    ]
