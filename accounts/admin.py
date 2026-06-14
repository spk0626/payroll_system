from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from employees.signals import _generate_secure_password
from .models import AdminAccount


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


class AdminAccountForm(forms.ModelForm):
    password_note = forms.CharField(
        label="Password",
        required=False,
        disabled=True,
        initial="Password is protected. Use reset password to send the user a new password.",
    )

    class Meta:
        model = AdminAccount
        fields = "__all__"
        help_texts = {
            "username": "Use the admin's email address.",
        }


@admin.register(AdminAccount)
class AdminAccountAdmin(UserAdmin):
    form = AdminAccountForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "first_name", "last_name", "password1", "password2"),
            },
        ),
        (
            "Admin access",
            {
                "fields": ("is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
    )
    fieldsets = (
        (None, {"fields": ("username", "email", "password_note")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Admin access", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("last_login", "date_joined")
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser", "is_active")
    actions = ["reset_admin_passwords"]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=True)

    def save_model(self, request, obj, form, change):
        obj.is_staff = True
        super().save_model(request, obj, form, change)

    @admin.action(description="Reset passwords and email selected admins")
    def reset_admin_passwords(self, request, queryset):
        count = 0
        from django.core.mail import send_mail
        from django.conf import settings

        for user in queryset:
            if not user.email:
                self.message_user(
                    request,
                    f"{user.username} does not have an email address.",
                    messages.ERROR,
                )
                continue
            password = _generate_secure_password()
            user.set_password(password)
            user.save(update_fields=["password"])
            send_mail(
                subject=f"{settings.COMPANY_NAME} admin password reset",
                message=(
                    f"Your admin password has been reset.\n\n"
                    f"Login: {settings.SITE_URL.rstrip('/')}/{settings.ADMIN_URL}\n"
                    f"Username: {user.username}\n"
                    f"Temporary password: {password}\n\n"
                    "Please change this password after signing in."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            count += 1

        self.message_user(
            request,
            f"Passwords reset for {count} admin account(s).",
            messages.SUCCESS,
        )
