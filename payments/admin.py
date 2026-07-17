"""Admin configuration for rent payments."""

from django.contrib import admin

from .models import RentPayment


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ("lease", "period_label", "amount", "late_fee",
                    "status", "payment_method", "payment_date")
    list_filter = ("status", "payment_method", "year", "month")
    search_fields = ("lease__tenant__user__first_name", "lease__tenant__user__last_name",
                     "lease__unit__unit_number", "lease__unit__property__title")
    ordering = ("-year", "-month")
    autocomplete_fields = ("lease",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Period")
    def period_label(self, obj):
        return obj.period_label
