"""Maintenance request model."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class MaintenanceQuerySet(models.QuerySet):
    """Scope maintenance requests by the requesting user's role."""

    def for_user(self, user):
        if user.is_admin:
            return self
        if user.is_owner:
            # Owners see requests on their own properties.
            return self.filter(unit__property__owner=user)
        # Tenants see requests they raised (or that name their profile).
        return self.filter(models.Q(created_by=user) | models.Q(tenant__user=user)).distinct()

    def open(self):
        """Anything not yet completed counts as an open ticket."""
        return self.exclude(status=MaintenanceRequest.Status.COMPLETED)


class MaintenanceRequest(models.Model):
    """A repair/maintenance ticket raised against a unit."""

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="maintenance_requests",
    )
    unit = models.ForeignKey(
        "properties.Unit",
        on_delete=models.CASCADE,
        related_name="maintenance_requests",
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    priority = models.CharField(
        max_length=8, choices=Priority.choices, default=Priority.MEDIUM,
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.OPEN,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_maintenance",
        limit_choices_to={"role__in": ["OWNER", "ADMIN"]},
    )
    estimated_cost = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    completed_date = models.DateField(null=True, blank=True)
    image = models.ImageField(upload_to="maintenance/", blank=True, null=True)

    # Audit: who raised the ticket.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="raised_maintenance",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MaintenanceQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} · {self.unit}"

    def get_absolute_url(self):
        return reverse("maintenance:detail", kwargs={"pk": self.pk})

    @property
    def is_open(self):
        return self.status != self.Status.COMPLETED

    def save(self, *args, **kwargs):
        # Keep completed_date consistent with status automatically.
        if self.status == self.Status.COMPLETED and not self.completed_date:
            self.completed_date = timezone.localdate()
        if self.status != self.Status.COMPLETED:
            self.completed_date = None
        super().save(*args, **kwargs)
