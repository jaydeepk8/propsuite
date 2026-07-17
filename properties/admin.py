"""Admin configuration for properties and units."""

from django.contrib import admin

from .models import Property, Unit


class UnitInline(admin.TabularInline):
    """Manage a property's units inline on the property page."""

    model = Unit
    extra = 1
    fields = ("unit_number", "floor", "bedrooms", "bathrooms",
              "rent_amount", "security_deposit", "status")


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "property_type", "city",
                    "status", "units_count", "created_at")
    list_filter = ("property_type", "status", "city", "country")
    search_fields = ("title", "address", "city", "state", "pincode",
                     "owner__username", "owner__email")
    ordering = ("-created_at",)
    autocomplete_fields = ("owner",)
    inlines = [UnitInline]
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Units")
    def units_count(self, obj):
        return obj.units_count


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("unit_number", "property", "floor", "bedrooms",
                    "bathrooms", "rent_amount", "status")
    list_filter = ("status", "bedrooms", "property__city")
    search_fields = ("unit_number", "property__title")
    ordering = ("property", "unit_number")
    autocomplete_fields = ("property",)
