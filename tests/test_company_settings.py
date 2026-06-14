from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase

from core.context_processors import company_settings
from core.models import CompanySetting


class TestCompanySettingsContext(TestCase):
    def test_logo_url_defaults_to_blank(self):
        context = company_settings(RequestFactory().get("/"))

        self.assertEqual(context["COMPANY_LOGO_URL"], "")

    def test_logo_url_is_exposed_when_uploaded(self):
        setting = CompanySetting.load()
        setting.logo.save("logo.txt", ContentFile(b"logo"), save=True)

        context = company_settings(RequestFactory().get("/"))

        self.assertIn("company/logo", context["COMPANY_LOGO_URL"])
