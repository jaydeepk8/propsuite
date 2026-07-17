"""Property and Unit models."""

import builtins
from decimal import Decimal
from io import BytesIO

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.urls import reverse


class PropertyQuerySet(models.QuerySet):
    """Reusable, chainable queries for properties."""

    def for_user(self, user):
        """Owners see only their own properties; admins see everything."""
        if user.is_admin:
            return self
        return self.filter(owner=user)

    def with_owner(self):
        return self.select_related("owner")


class Property(models.Model):
    """A building/estate owned by a property owner; holds many units."""

    class PropertyType(models.TextChoices):
        RESIDENTIAL = "RESIDENTIAL", "Residential"
        COMMERCIAL = "COMMERCIAL", "Commercial"
        MIXED_USE = "MIXED_USE", "Mixed Use"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PENDING = "PENDING", "Pending"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        INACTIVE = "INACTIVE", "Inactive"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
        limit_choices_to={"role__in": ["OWNER", "ADMIN"]},
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    property_type = models.CharField(
        max_length=15,
        choices=PropertyType.choices,
        default=PropertyType.RESIDENTIAL,
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    # Address
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    country = models.CharField(max_length=80, default="India")
    pincode = models.CharField(max_length=12)

    image = models.ImageField(upload_to="properties/", blank=True, null=True)
    # Auto-generated QR code linking to this property's detail page.
    qr_code = models.ImageField(upload_to="qr/", blank=True, null=True)

    # Declared capacity. The *actual* number of Unit rows is `units.count()`;
    # this is the owner-stated target, kept per the project spec.
    total_units = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Planned number of units in this property.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PropertyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "properties"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("properties:detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Generate the QR code once, after the row has a pk (needed for the URL).
        # Skipped under the test runner so the suite doesn't litter media/.
        if not self.qr_code and not getattr(settings, "TESTING", False):
            self.generate_qr()

    def generate_qr(self):
        """(Re)build the property's QR code image pointing at its detail page."""
        target = f"{settings.SITE_URL.rstrip('/')}{self.get_absolute_url()}"
        img = qrcode.make(target)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        self.qr_code.save(
            f"property_{self.pk}.png",
            ContentFile(buffer.getvalue()),
            save=False,
        )
        # Persist only the qr_code column to avoid re-triggering generation.
        super().save(update_fields=["qr_code"])

    @property
    def full_address(self):
        parts = [self.address, self.city, self.state, self.pincode]
        return ", ".join(p for p in parts if p)

    # ── Unit roll-ups (used on cards and stat tiles) ──
    @property
    def units_count(self):
        return self.units.count()

    @property
    def occupied_count(self):
        return self.units.filter(status=Unit.Status.OCCUPIED).count()

    @property
    def vacant_count(self):
        return self.units.filter(status=Unit.Status.AVAILABLE).count()

    @property
    def maintenance_count(self):
        return self.units.filter(status=Unit.Status.MAINTENANCE).count()

    @property
    def occupancy_rate(self):
        total = self.units_count
        return round((self.occupied_count / total) * 100, 1) if total else 0.0

    @property
    def monthly_income(self):
        """Sum of rent for currently occupied units."""
        agg = self.units.filter(status=Unit.Status.OCCUPIED).aggregate(
            total=Sum("rent_amount")
        )
        return agg["total"] or Decimal("0.00")


class Unit(models.Model):
    """A rentable unit (flat/office/suite) within a property."""

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        OCCUPIED = "OCCUPIED", "Occupied"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="units",
    )
    unit_number = models.CharField(max_length=30)
    floor = models.IntegerField(default=0)
    bedrooms = models.PositiveSmallIntegerField(default=1)
    bathrooms = models.PositiveSmallIntegerField(default=1)
    rent_amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    security_deposit = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["property", "unit_number"]
        # A unit number is unique within its property.
        constraints = [
            models.UniqueConstraint(
                fields=["property", "unit_number"],
                name="unique_unit_number_per_property",
            )
        ]

    def __str__(self):
        return f"{self.property.title} · Unit {self.unit_number}"

    def get_absolute_url(self):
        return reverse("properties:detail", kwargs={"pk": self.property_id})

    # NOTE: the `property` FK above shadows the built-in `property` inside
    # this class body, so we reference it via `builtins`.
    @builtins.property
    def is_available(self):
        return self.status == self.Status.AVAILABLE
