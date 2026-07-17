"""Admin configuration for leases."""

from django.contrib import admin

from .models import Lease


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = ("tenant", "unit", "start_date", "end_date",
                    "monthly_rent", "status")
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("tenant__user__first_name", "tenant__user__last_name",
                     "unit__unit_number", "unit__property__title")
    ordering = ("-start_date",)
    autocomplete_fields = ("tenant", "unit")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "start_date"
