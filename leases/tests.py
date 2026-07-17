"""Tests for leases: signal-driven unit-status sync, validation, CRUD, command."""

from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Property, Unit
from tenants.models import Tenant
from leases.models import Lease


def make_unit(owner, number="101", status="AVAILABLE", rent="1500"):
    prop = Property.objects.create(
        owner=owner, title="P", property_type="RESIDENTIAL", status="ACTIVE",
        address="x", city="Austin", state="TX", country="USA", pincode="1")
    return Unit.objects.create(property=prop, unit_number=number,
                               rent_amount=Decimal(rent), status=status)


def make_tenant(owner, email="t@x.com"):
    u = User.objects.create_user(email, email, "p", role="TENANT")
    return Tenant.objects.create(user=u, created_by=owner)


class UnitStatusSignalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")

    def test_active_lease_occupies_unit(self):
        unit = make_unit(self.owner)
        tenant = make_tenant(self.owner)
        today = timezone.localdate()
        Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
            end_date=today + timedelta(days=365), monthly_rent=Decimal("1500"),
            status="ACTIVE")
        unit.refresh_from_db()
        self.assertEqual(unit.status, "OCCUPIED")

    def test_pending_lease_keeps_unit_available(self):
        unit = make_unit(self.owner)
        tenant = make_tenant(self.owner)
        today = timezone.localdate()
        Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
            end_date=today + timedelta(days=365), monthly_rent=Decimal("1500"),
            status="PENDING")
        unit.refresh_from_db()
        self.assertEqual(unit.status, "AVAILABLE")

    def test_expiring_lease_frees_unit(self):
        unit = make_unit(self.owner)
        tenant = make_tenant(self.owner)
        today = timezone.localdate()
        lease = Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
            end_date=today + timedelta(days=365), monthly_rent=Decimal("1500"),
            status="ACTIVE")
        unit.refresh_from_db()
        self.assertEqual(unit.status, "OCCUPIED")
        # Now expire it.
        lease.status = "EXPIRED"
        lease.save()
        unit.refresh_from_db()
        self.assertEqual(unit.status, "AVAILABLE")

    def test_deleting_active_lease_frees_unit(self):
        unit = make_unit(self.owner)
        tenant = make_tenant(self.owner)
        today = timezone.localdate()
        lease = Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
            end_date=today + timedelta(days=365), monthly_rent=Decimal("1500"),
            status="ACTIVE")
        lease.delete()
        unit.refresh_from_db()
        self.assertEqual(unit.status, "AVAILABLE")

    def test_maintenance_unit_not_freed(self):
        unit = make_unit(self.owner, status="MAINTENANCE")
        tenant = make_tenant(self.owner)
        today = timezone.localdate()
        # A pending lease shouldn't disturb a maintenance unit.
        Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
            end_date=today + timedelta(days=10), monthly_rent=Decimal("1"),
            status="PENDING")
        unit.refresh_from_db()
        self.assertEqual(unit.status, "MAINTENANCE")


class LeaseValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")

    def setUp(self):
        self.client.login(username="own@x.com", password="Pass!2345")

    def test_available_units_only_in_form(self):
        avail = make_unit(self.owner, "101", "AVAILABLE")
        make_unit(self.owner, "102", "OCCUPIED")
        make_tenant(self.owner)
        r = self.client.get(reverse("leases:create"))
        units = list(r.context["form"].fields["unit"].queryset)
        self.assertIn(avail, units)
        self.assertEqual(len(units), 1)  # occupied one excluded

    def test_end_before_start_rejected(self):
        unit = make_unit(self.owner)
        tenant = make_tenant(self.owner)
        today = timezone.localdate()
        r = self.client.post(reverse("leases:create"), {
            "tenant": tenant.pk, "unit": unit.pk,
            "start_date": today, "end_date": today - timedelta(days=1),
            "monthly_rent": "1500", "security_deposit": "0", "status": "ACTIVE"})
        self.assertEqual(r.status_code, 200)  # re-render with errors
        self.assertFalse(Lease.objects.exists())


class ExpireLeasesCommandTests(TestCase):
    def test_command_expires_and_activates(self):
        owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        today = timezone.localdate()

        # Past-due active lease -> should expire and free its unit.
        u1 = make_unit(owner, "1")
        t1 = make_tenant(owner, "a@x.com")
        past = Lease.objects.create(tenant=t1, unit=u1,
            start_date=today - timedelta(days=400),
            end_date=today - timedelta(days=1),
            monthly_rent=Decimal("1"), status="ACTIVE")

        # Pending lease whose term has started -> should activate.
        u2 = make_unit(owner, "2")
        t2 = make_tenant(owner, "b@x.com")
        pend = Lease.objects.create(tenant=t2, unit=u2,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=30),
            monthly_rent=Decimal("1"), status="PENDING")

        call_command("expire_leases")

        past.refresh_from_db(); pend.refresh_from_db()
        u1.refresh_from_db(); u2.refresh_from_db()
        self.assertEqual(past.status, "EXPIRED")
        self.assertEqual(u1.status, "AVAILABLE")
        self.assertEqual(pend.status, "ACTIVE")
        self.assertEqual(u2.status, "OCCUPIED")
