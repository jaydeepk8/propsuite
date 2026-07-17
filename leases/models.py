"""Lease model — binds a tenant to a unit for a term."""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class LeaseQuerySet(models.QuerySet):
    """Scope leases by the requesting user."""

    def for_user(self, user):
        """Admins see all; owners see leases on their own units."""
        if user.is_admin:
            return self
        return self.filter(unit__property__owner=user)

    def active(self):
        return self.filter(status=Lease.Status.ACTIVE)


class Lease(models.Model):
    """A rental agreement for one unit and one tenant over a date range."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="leases",
    )
    unit = models.ForeignKey(
        "properties.Unit",
        on_delete=models.CASCADE,
        related_name="leases",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = LeaseQuerySet.as_manager()

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.tenant} · {self.unit} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("leases:detail", kwargs={"pk": self.pk})

    def clean(self):
        """Model-level validation shared by forms and the admin."""
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})

    @property
    def is_expired(self):
        return self.end_date < timezone.localdate()

    @property
    def days_to_expiry(self):
        return (self.end_date - timezone.localdate()).days
