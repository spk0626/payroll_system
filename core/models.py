from django.db import models
from django.utils.translation import gettext_lazy as _


class CompanySetting(models.Model):
    """Singleton company branding settings managed from the admin portal."""

    logo = models.FileField(
        upload_to="company/",
        blank=True,
        verbose_name=_("Company logo"),
        help_text=_("Shown on login screens, admin header, employee portal, and payslips."),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Company setting")
        verbose_name_plural = _("Company settings")

    def __str__(self) -> str:
        return "Company settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
