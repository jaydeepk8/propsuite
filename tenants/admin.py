"""Admin configuration for tenants."""

from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "phone", "occupation", "created_by", "created_at")
    list_filter = ("occupation", "created_at")
    search_fields = ("user__first_name", "user__last_name", "user__email", "phone")
    ordering = ("user__first_name",)
    autocomplete_fields = ("user", "created_by")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.full_name

    @admin.display(description="Email")
    def email(self, obj):
        return obj.email
