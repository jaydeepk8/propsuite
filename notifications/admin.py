"""Admin configuration for notifications."""

from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "kind", "is_read", "created_at")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("title", "message", "user__username", "user__email")
    ordering = ("-created_at",)
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
    actions = ["mark_read", "mark_unread"]

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_read=True)} marked read.")

    @admin.action(description="Mark selected as unread")
    def mark_unread(self, request, queryset):
        self.message_user(request, f"{queryset.update(is_read=False)} marked unread.")
