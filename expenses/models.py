"""Expense tracking model (bonus feature)."""

import builtins
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class ExpenseQuerySet(models.QuerySet):
    def for_user(self, user):
        """Admins see all; owners see expenses on their own properties."""
        if user.is_admin:
            return self
        return self.filter(property__owner=user)


class Expense(models.Model):
    """A cost incurred against a property (utilities, tax, repairs, …)."""

    class Category(models.TextChoices):
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        UTILITIES = "UTILITIES", "Utilities"
        TAX = "TAX", "Property Tax"
        INSURANCE = "INSURANCE", "Insurance"
        MANAGEMENT = "MANAGEMENT", "Management"
        OTHER = "OTHER", "Other"

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    category = models.CharField(
        max_length=12, choices=Category.choices, default=Category.OTHER,
    )
    title = models.CharField(max_length=150)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    date = models.DateField()
    vendor = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="logged_expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ExpenseQuerySet.as_manager()

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.title} — ₹{self.amount}"

    def get_absolute_url(self):
        return reverse("expenses:list")

    # `property` FK shadows the built-in decorator inside the class body.
    @builtins.property
    def category_badge_class(self):
        return {
            self.Category.MAINTENANCE: "rw-badge-blue",
            self.Category.UTILITIES: "rw-badge-amber",
            self.Category.TAX: "rw-badge-red",
            self.Category.INSURANCE: "rw-badge-green",
            self.Category.MANAGEMENT: "rw-badge-gray",
        }.get(self.category, "rw-badge-gray")
