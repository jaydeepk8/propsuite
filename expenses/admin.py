"""Admin configuration for expenses."""

from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "property", "category", "amount", "date", "vendor")
    list_filter = ("category", "date")
    search_fields = ("title", "vendor", "property__title", "notes")
    ordering = ("-date",)
    autocomplete_fields = ("property",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "date"
