# Generated manually for HR branding settings.

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CompanySetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("logo", models.FileField(blank=True, help_text="Shown on login screens, admin header, employee portal, and payslips.", upload_to="company/", verbose_name="Company logo")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Company setting",
                "verbose_name_plural": "Company settings",
            },
        ),
    ]
