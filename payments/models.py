"""Rent payment model."""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

MONTH_CHOICES = [
    (1, "January"), (2, "February"), (3, "March"), (4, "April"),
    (5, "May"), (6, "June"), (7, "July"), (8, "August"),
    (9, "September"), (10, "October"), (11, "November"), (12, "December"),
]


class RentPaymentQuerySet(models.QuerySet):
    """Scope payments by user and provide handy aggregates."""

    def for_user(self, user):
        """Admins see all; owners see payments for leases on their units."""
        if user.is_admin:
            return self
        return self.filter(lease__unit__property__owner=user)

    def paid(self):
        return self.filter(status=RentPayment.Status.PAID)

    def pending(self):
        return self.filter(status=RentPayment.Status.PENDING)

    def overdue(self):
        """Pending payments whose due date has passed (computed, not stored)."""
        return self.filter(
            status=RentPayment.Status.PENDING,
            due_date__lt=timezone.localdate(),
        )


class RentPayment(models.Model):
    """
    A single month's rent for a lease.

    Only PAID / PENDING are stored. "Overdue" is *derived* from a pending
    payment whose due date has passed, so it can never go stale.
    """

    class Status(models.TextChoices):
        PAID = "PAID", "Paid"
        PENDING = "PENDING", "Pending"

    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK = "BANK", "Bank Transfer"
        UPI = "UPI", "UPI"
        CARD = "CARD", "Card"
        CHEQUE = "CHEQUE", "Cheque"

    lease = models.ForeignKey(
        "leases.Lease",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    month = models.PositiveSmallIntegerField(
        choices=MONTH_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    year = models.PositiveIntegerField()
    due_date = models.DateField()
    payment_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    late_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    payment_method = models.CharField(
        max_length=10, choices=Method.choices, blank=True,
    )
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RentPaymentQuerySet.as_manager()

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            # One rent record per lease per month — makes the monthly-rent
            # generator safe to re-run.
            models.UniqueConstraint(
                fields=["lease", "month", "year"],
                name="unique_payment_per_lease_month",
            )
        ]

    def __str__(self):
        return f"{self.lease.tenant} · {self.period_label} · {self.get_status_display()}"

    def get_absolute_url(self):
        return reverse("payments:detail", kwargs={"pk": self.pk})

    # ── Derived values ──
    @property
    def period_label(self):
        return f"{self.get_month_display()[:3]} {self.year}"

    @property
    def is_overdue(self):
        return (self.status == self.Status.PENDING
                and self.due_date < timezone.localdate())

    @property
    def effective_status(self):
        """PAID / PENDING / OVERDUE for display and badges."""
        if self.is_overdue:
            return "OVERDUE"
        return self.status

    @property
    def effective_status_display(self):
        return {"PAID": "Paid", "PENDING": "Pending", "OVERDUE": "Overdue"}[self.effective_status]

    @property
    def total_due(self):
        return self.amount + self.late_fee

    @property
    def receipt_number(self):
        return f"RCPT-{self.year}{self.month:02d}-{self.pk:05d}"

    def mark_paid(self, method=None, when=None):
        """Record this payment as paid (used by the quick action)."""
        self.status = self.Status.PAID
        self.payment_date = when or timezone.localdate()
        if method:
            self.payment_method = method
        self.save(update_fields=["status", "payment_date", "payment_method", "updated_at"])
