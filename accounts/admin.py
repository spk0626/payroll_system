from django import forms
from django.contrib import admin, messages
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ImproperlyConfigured
from django.core.validators import RegexValidator
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from core.admin_mixins import ActionLabelMixin
from .models import AdminAccount


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


alphanumeric_validator = RegexValidator(
    regex=r"^[a-zA-Z0-9]+$",
    message="Username may only contain letters and numbers.",
)


class AdminAccountForm(forms.ModelForm):
    username = forms.CharField(validators=[alphanumeric_validator])
    password_note = forms.CharField(
        label="Password",
        required=False,
        disabled=True,
        initial="Password is protected. Use the reset email button to let the user set a new password.",
    )

    class Meta:
        model = AdminAccount
        fields = "__all__"
        help_texts = {
            "username": "Letters and numbers only.",
        }


class AdminAccountCreationForm(UserAdmin.add_form):
    username = forms.CharField(validators=[alphanumeric_validator])


@admin.register(AdminAccount)
class AdminAccountAdmin(ActionLabelMixin, UserAdmin):
    form = AdminAccountForm
    add_form = AdminAccountCreationForm
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
        (None, {"fields": ("username", "email", "password_note", "password_reset_email")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Admin access", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("last_login", "date_joined", "password_reset_email")
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser", "is_active")
    actions = ["reset_admin_passwords"]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:user_id>/send-password-reset/",
                self.admin_site.admin_view(self.send_password_reset_email),
                name="accounts_adminaccount_send_password_reset",
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        role = request.GET.get("role", "admin")
        if role == "employee":
            return queryset.filter(is_staff=False)
        return queryset.filter(is_staff=True)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_staff = True
        elif obj.is_staff:
            obj.is_staff = True
        super().save_model(request, obj, form, change)

    def password_reset_email(self, obj):
        if not obj or not obj.pk:
            return "Save this account before sending a reset email."
        if not obj.email:
            return "Add an email address before sending a reset email."
        url = reverse("admin:accounts_adminaccount_send_password_reset", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}"><i class="ti ti-mail" aria-hidden="true"></i> '
            "Send password reset email</a>",
            url,
        )

    password_reset_email.short_description = "Reset access"

    def _send_password_reset(self, request, user):
        from django.conf import settings

        backend = getattr(settings, "EMAIL_BACKEND", "")
        if not backend or backend.endswith(".dummy.EmailBackend"):
            raise ImproperlyConfigured(
                "Email backend is not configured. Set EMAIL_BACKEND/SMTP settings before sending reset emails."
            )
        form = PasswordResetForm({"email": user.email})
        if not form.is_valid():
            raise ValueError("The account email address is not valid for password reset.")
        form.save(
            request=request,
            use_https=request.is_secure(),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            email_template_name="accounts/email/password_reset.txt",
            subject_template_name="accounts/email/password_reset_subject.txt",
            extra_email_context={"COMPANY_NAME": settings.COMPANY_NAME},
        )

    def send_password_reset_email(self, request, user_id):
        user = self.get_object(request, user_id)
        if not user:
            self.message_user(request, "Admin account not found.", messages.ERROR)
            return redirect("admin:accounts_adminaccount_changelist")
        if not user.email:
            self.message_user(request, "Add an email address before sending a reset email.", messages.ERROR)
            return redirect("admin:accounts_adminaccount_change", user.pk)
        try:
            self._send_password_reset(request, user)
        except (ImproperlyConfigured, ValueError) as exc:
            self.message_user(request, str(exc), messages.ERROR)
        else:
            self.message_user(request, f"Password reset email sent to {user.email}.", messages.SUCCESS)
        return redirect("admin:accounts_adminaccount_change", user.pk)

    @admin.action(description="Send password reset email to selected admins")
    def reset_admin_passwords(self, request, queryset):
        count = 0

        for user in queryset:
            if not user.email:
                self.message_user(
                    request,
                    f"{user.username} does not have an email address.",
                    messages.ERROR,
                )
                continue
            try:
                self._send_password_reset(request, user)
            except (ImproperlyConfigured, ValueError) as exc:
                self.message_user(request, str(exc), messages.ERROR)
                return
            else:
                count += 1

        self.message_user(
            request,
            f"Password reset email sent for {count} admin account(s).",
            messages.SUCCESS,
        )


@admin.register(Group)
class PayrollGroupAdmin(ActionLabelMixin, GroupAdmin):
    pass
