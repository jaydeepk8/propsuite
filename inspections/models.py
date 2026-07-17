"""Property inspection model."""

import builtins

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class InspectionQuerySet(models.QuerySet):
    """Scope inspections to what the requesting user may see."""

    def for_user(self, user):
        """Admins see all; owners see inspections on their own properties."""
        if user.is_admin:
            return self
        return self.filter(property__owner=user)

    def upcoming(self):
        return self.filter(
            status=Inspection.Status.SCHEDULED,
            inspection_date__gte=timezone.localdate(),
        )


class Inspection(models.Model):
    """
    A scheduled inspection of a property (optionally a specific unit).

    Owners schedule inspections and later attach a report file.
    """

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="inspections",
    )
    # Optional — an inspection may cover the whole property.
    unit = models.ForeignKey(
        "properties.Unit",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="inspections",
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="inspections",
        limit_choices_to={"role__in": ["OWNER", "ADMIN"]},
    )
    inspection_date = models.DateField()
    notes = models.TextField(blank=True)
    report = models.FileField(
        upload_to="inspections/",
        blank=True, null=True,
        validators=[FileExtensionValidator(
            ["pdf", "doc", "docx", "jpg", "jpeg", "png"]
        )],
        help_text="PDF, Word document or image.",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.SCHEDULED,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="scheduled_inspections",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InspectionQuerySet.as_manager()

    class Meta:
        ordering = ["-inspection_date"]

    def __str__(self):
        target = f"{self.property.title}"
        if self.unit_id:
            target += f" · Unit {self.unit.unit_number}"
        return f"{target} — {self.inspection_date}"

    def get_absolute_url(self):
        return reverse("inspections:detail", kwargs={"pk": self.pk})

    def clean(self):
        """A chosen unit must belong to the chosen property."""
        if self.unit_id and self.property_id and self.unit.property_id != self.property_id:
            raise ValidationError({"unit": "That unit doesn't belong to the selected property."})

    # NOTE: the `property` FK above shadows the built-in `property` inside
    # this class body, so we reference it via `builtins`.
    @builtins.property
    def is_upcoming(self):
        return (self.status == self.Status.SCHEDULED
                and self.inspection_date >= timezone.localdate())

    @builtins.property
    def is_overdue(self):
        """Still scheduled but the date has passed."""
        return (self.status == self.Status.SCHEDULED
                and self.inspection_date < timezone.localdate())

    @builtins.property
    def has_report(self):
        return bool(self.report)
