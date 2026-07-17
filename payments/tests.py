"""Tests for payments: computed Overdue, uniqueness, mark-paid, filters, command."""

from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Property, Unit
from tenants.models import Tenant
from leases.models import Lease
from payments.models import RentPayment


from itertools import count

_seq = count(1)


def build_lease(owner, rent="1500", status="ACTIVE"):
    """Create a fresh property/unit/tenant/lease with unique identifiers."""
    n = next(_seq)
    prop = Property.objects.create(owner=owner, title=f"P{n}", property_type="RESIDENTIAL",
        status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")
    unit = Unit.objects.create(property=prop, unit_number=f"U{n}", rent_amount=Decimal(rent))
    u = User.objects.create_user(f"t{n}@x.com", f"t{n}@x.com", "p", role="TENANT")
    tenant = Tenant.objects.create(user=u, created_by=owner)
    today = timezone.localdate()
    return Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
        end_date=today + timedelta(days=365), monthly_rent=Decimal(rent), status=status)


class RentPaymentModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.lease = build_lease(cls.owner)

    def test_overdue_is_computed(self):
        today = timezone.localdate()
        p = RentPayment.objects.create(lease=self.lease, month=1, year=2020,
            due_date=today - timedelta(days=5), amount=Decimal("1500"), status="PENDING")
        self.assertTrue(p.is_overdue)
        self.assertEqual(p.effective_status, "OVERDUE")

    def test_pending_future_not_overdue(self):
        today = timezone.localdate()
        p = RentPayment.objects.create(lease=self.lease, month=1, year=2099,
            due_date=today + timedelta(days=5), amount=Decimal("1500"), status="PENDING")
        self.assertFalse(p.is_overdue)
        self.assertEqual(p.effective_status, "PENDING")

    def test_paid_never_overdue(self):
        today = timezone.localdate()
        p = RentPayment.objects.create(lease=self.lease, month=2, year=2020,
            due_date=today - timedelta(days=30), amount=Decimal("1500"),
            status="PAID", payment_date=today)
        self.assertFalse(p.is_overdue)
        self.assertEqual(p.effective_status, "PAID")

    def test_total_due_includes_late_fee(self):
        p = RentPayment.objects.create(lease=self.lease, month=3, year=2025,
            due_date=timezone.localdate(), amount=Decimal("1500"), late_fee=Decimal("100"))
        self.assertEqual(p.total_due, Decimal("1600"))

    def test_unique_per_lease_month_year(self):
        RentPayment.objects.create(lease=self.lease, month=4, year=2025,
            due_date=timezone.localdate(), amount=Decimal("1500"))
        with self.assertRaises(IntegrityError):
            RentPayment.objects.create(lease=self.lease, month=4, year=2025,
                due_date=timezone.localdate(), amount=Decimal("1500"))


class PaymentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.lease = build_lease(cls.owner)

    def setUp(self):
        self.client.login(username="own@x.com", password="Pass!2345")

    def test_mark_paid_flow(self):
        today = timezone.localdate()
        p = RentPayment.objects.create(lease=self.lease, month=5, year=2025,
            due_date=today, amount=Decimal("1500"), status="PENDING")
        self.client.post(reverse("payments:mark_paid", args=[p.pk]),
            {"payment_method": "UPI", "payment_date": today, "late_fee": "50"})
        p.refresh_from_db()
        self.assertEqual(p.status, "PAID")
        self.assertEqual(p.payment_method, "UPI")
        self.assertEqual(p.late_fee, Decimal("50"))

    def test_list_stats_and_overdue_filter(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=1, year=2020,
            due_date=today - timedelta(days=5), amount=Decimal("1000"), status="PENDING")  # overdue
        RentPayment.objects.create(lease=self.lease, month=2, year=2025,
            due_date=today, amount=Decimal("2000"), status="PAID", payment_date=today)     # collected
        r = self.client.get(reverse("payments:list"))
        self.assertEqual(r.context["stats"]["collected"], Decimal("2000"))
        self.assertEqual(r.context["stats"]["overdue_count"], 1)
        # Overdue filter returns only the overdue one.
        r2 = self.client.get(reverse("payments:list") + "?status=OVERDUE")
        self.assertEqual(len(r2.context["object_list"]), 1)

    def test_ownership_isolation(self):
        other = User.objects.create_user("o2", "o2@x.com", "p", role="OWNER")
        lease2 = build_lease(other)
        p = RentPayment.objects.create(lease=lease2, month=6, year=2025,
            due_date=timezone.localdate(), amount=Decimal("1"))
        self.assertEqual(self.client.get(reverse("payments:detail", args=[p.pk])).status_code, 404)


class GenerateMonthlyRentCommandTests(TestCase):
    def test_generates_once_and_is_idempotent(self):
        owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        lease = build_lease(owner, rent="1800", status="ACTIVE")
        build_lease(owner, status="PENDING")  # inactive lease — should be skipped
        # second active lease uses a different tenant/unit
        call_command("generate_monthly_rent", "--month", "7", "--year", "2026")
        self.assertEqual(RentPayment.objects.filter(month=7, year=2026).count(), 1)
        p = RentPayment.objects.get(month=7, year=2026)
        self.assertEqual(p.amount, Decimal("1800"))
        self.assertEqual(p.status, "PENDING")
        # Re-run: no duplicates.
        call_command("generate_monthly_rent", "--month", "7", "--year", "2026")
        self.assertEqual(RentPayment.objects.filter(month=7, year=2026).count(), 1)
