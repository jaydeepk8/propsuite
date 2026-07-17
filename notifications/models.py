"""In-app notification model."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(is_read=False)

    def for_user(self, user):
        return self.filter(user=user)


class Notification(models.Model):
    """
    A single in-app notification addressed to one user.

    Created by the signal receivers in `notifications/signals.py` and by the
    reminder management commands — never directly from views.
    """

    class Kind(models.TextChoices):
        RENT_DUE = "RENT_DUE", "Rent due"
        PAYMENT_RECEIVED = "PAYMENT_RECEIVED", "Payment received"
        LEASE_EXPIRY = "LEASE_EXPIRY", "Lease expiry"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        INSPECTION = "INSPECTION", "Inspection"
        GENERAL = "GENERAL", "General"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True)
    # Where clicking the notification takes the user.
    url = models.CharField(max_length=300, blank=True)
    kind = models.CharField(
        max_length=20, choices=Kind.choices, default=Kind.GENERAL,
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # The navbar badge counts unread rows on every request.
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.title}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=["is_read"])

    @property
    def icon(self):
        """Bootstrap icon name for this notification kind."""
        return {
            self.Kind.RENT_DUE: "bi-cash-coin",
            self.Kind.PAYMENT_RECEIVED: "bi-check-circle",
            self.Kind.LEASE_EXPIRY: "bi-file-earmark-text",
            self.Kind.MAINTENANCE: "bi-wrench-adjustable",
            self.Kind.INSPECTION: "bi-clipboard-check",
        }.get(self.kind, "bi-bell")

    @property
    def badge_class(self):
        return {
            self.Kind.RENT_DUE: "rw-badge-amber",
            self.Kind.PAYMENT_RECEIVED: "rw-badge-green",
            self.Kind.LEASE_EXPIRY: "rw-badge-amber",
            self.Kind.MAINTENANCE: "rw-badge-blue",
            self.Kind.INSPECTION: "rw-badge-blue",
        }.get(self.kind, "rw-badge-gray")
