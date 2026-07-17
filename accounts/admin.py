"""Admin configuration for the accounts app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Custom-user admin: reuses Django's UserAdmin with our extra fields."""

    list_display = ("username", "email", "role", "phone", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    ordering = ("username",)

    # Add our custom fields to the default UserAdmin fieldsets.
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("PropSuite profile", {"fields": ("role", "phone", "profile_image")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("PropSuite profile", {"fields": ("email", "role", "phone")}),
    )
