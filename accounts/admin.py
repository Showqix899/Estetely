"""Show the User and Profile tables in the Django admin (/admin/)."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm as BaseUserChangeForm

from .models import Profile, User


class UserCreationForm(BaseUserCreationForm):
    """Form used on the admin 'Add user' page."""

    class Meta:
        model = User
        fields = ("email", "full_name", "role")


class UserChangeForm(BaseUserChangeForm):
    """Form used on the admin 'Change user' page."""

    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserChangeForm
    ordering = ("email",)
    list_display = ("email", "full_name", "role", "is_staff")
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "role", "password1", "password2")}),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "city")
