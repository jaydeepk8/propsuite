"""Admin configuration for inspections."""

from django.contrib import admin

from .models import Inspection


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("property", "unit", "inspector", "inspection_date",
                    "status", "has_report")
    list_filter = ("status", "inspection_date")
    search_fields = ("property__title", "unit__unit_number", "notes")
    ordering = ("-inspection_date",)
    autocomplete_fields = ("property", "unit", "inspector")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "inspection_date"

    @admin.display(boolean=True, description="Report")
    def has_report(self, obj):
        return obj.has_report
