"""Admin configuration for maintenance requests."""

from django.contrib import admin

from .models import MaintenanceRequest


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "unit", "tenant", "priority", "status",
                    "assigned_to", "estimated_cost", "created_at")
    list_filter = ("status", "priority", "created_at")
    search_fields = ("title", "description", "unit__unit_number",
                     "unit__property__title",
                     "tenant__user__first_name", "tenant__user__last_name")
    ordering = ("-created_at",)
    autocomplete_fields = ("unit", "tenant", "assigned_to")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
