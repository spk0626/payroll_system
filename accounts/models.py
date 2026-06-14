from django.contrib.auth.models import User


class AdminAccount(User):
    class Meta:
        proxy = True
        verbose_name = "Admin account"
        verbose_name_plural = "Admin accounts"
