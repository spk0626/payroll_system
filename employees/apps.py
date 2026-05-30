from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "employees"
    verbose_name = "Employees"

    def ready(self) -> None:
        import employees.signals  # noqa: F401 — registers signal handlers