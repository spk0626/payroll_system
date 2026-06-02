from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase


def _field_names(fieldsets):
    for _, options in fieldsets or []:
        for field in options.get("fields", []):
            if isinstance(field, (list, tuple)):
                yield from field
            else:
                yield field


class TestAdminConfiguration(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.user = User.objects.create_superuser(
            "admin@test.com", "admin@test.com", "Admin!Pass123"
        )

    def test_non_editable_fieldset_fields_are_readonly(self):
        """
        Django raises FieldError when a non-editable model field appears in
        admin fieldsets unless the admin marks it as read-only.
        """
        failures = []

        for model, model_admin in admin.site._registry.items():
            failures.extend(self._non_readonly_fields(model, model_admin))

            for inline_class in model_admin.inlines:
                inline = inline_class(model, admin.site)
                failures.extend(self._non_readonly_fields(inline.model, inline))

        self.assertEqual(failures, [])

    def _non_readonly_fields(self, model, admin_obj):
        readonly_fields = set(admin_obj.get_readonly_fields(self.request))
        model_fields = {
            field.name: field
            for field in model._meta.get_fields()
            if getattr(field, "concrete", False)
        }
        failures = []

        for field_name in _field_names(getattr(admin_obj, "fieldsets", None)):
            field = model_fields.get(field_name)
            if field and not field.editable and field_name not in readonly_fields:
                failures.append(
                    f"{admin_obj.__class__.__name__}.{field_name} must be in readonly_fields"
                )

        return failures
