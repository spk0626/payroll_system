# Generated manually for HR bank account details.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="bank_account_number",
            field=models.CharField(blank=True, max_length=50, verbose_name="Bank account number"),
        ),
    ]
