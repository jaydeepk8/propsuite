"""Tests for dashboard routing, selectors and role scoping."""

from datetime import timedelta
from decimal import Decimal
from itertools import count

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Property, Unit
from tenants.models import Tenant
from leases.models import Lease
from payments.models import RentPayment
from maintenance.models import MaintenanceRequest
from dashboard import selectors

_seq = count(1)


def build_world(owner, rent="1000"):
    n = next(_seq)
    prop = Property.objects.create(owner=owner, title=f"P{n}", property_type="RESIDENTIAL",
        status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")
    unit = Unit.objects.create(property=prop, unit_number=f"U{n}", rent_amount=Decimal(rent))
    tu = User.objects.create_user(f"t{n}@x.com", f"t{n}@x.com", "Pass!2345", role="TENANT")
    tenant = Tenant.objects.create(user=tu, created_by=owner)
    today = timezone.localdate()
    lease = Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
        end_date=today + timedelta(days=365), monthly_rent=Decimal(rent), status="ACTIVE")
    return prop, unit, tenant, lease


class DashboardRoutingTests(TestCase):
    def test_each_role_lands_on_its_dashboard(self):
        cases = [
            ("admin@x.com", "ADMIN", "/admin/"),
            ("owner@x.com", "OWNER", "/owner/"),
            ("ten@x.com", "TENANT", "/tenant/"),
        ]
        for email, role, suffix in cases:
            User.objects.create_user(email, email, "Pass!2345", role=role)
            self.client.login(username=email, password="Pass!2345")
            r = self.client.get(reverse("dashboard:redirect"))
            self.assertEqual(r.status_code, 302)
            self.assertTrue(r.url.endswith(suffix), f"{role} -> {r.url}")
            self.client.logout()

    def test_owner_cannot_open_admin_dashboard(self):
        User.objects.create_user("o@x.com", "o@x.com", "Pass!2345", role="OWNER")
        self.client.login(username="o@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 403)


class OwnerSelectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.other = User.objects.create_user("o2", "o2@x.com", "Pass!2345", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner, "1000")
        # Another owner's world must never leak into our numbers.
        build_world(cls.other, "9999")

    def test_stats_scoped_to_owner(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=today.month, year=today.year,
            due_date=today, amount=Decimal("1000"), status="PAID", payment_date=today)
        data = selectors.owner_dashboard(self.owner)
        s = data["stats"]
        self.assertEqual(s["total_properties"], 1)          # not 2
        self.assertEqual(s["occupied_units"], 1)            # lease is active
        self.assertEqual(s["monthly_revenue"], Decimal("1000"))
        self.assertEqual(s["occupancy_rate"], 100.0)

    def test_pending_and_late_counts(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=1, year=2020,
            due_date=today - timedelta(days=5), amount=Decimal("500"), status="PENDING")
        s = selectors.owner_dashboard(self.owner)["stats"]
        self.assertEqual(s["pending_rent"], Decimal("500"))
        self.assertEqual(s["late_count"], 1)

    def test_maintenance_counts(self):
        MaintenanceRequest.objects.create(unit=self.unit, title="A", priority="HIGH", status="OPEN")
        MaintenanceRequest.objects.create(unit=self.unit, title="B", priority="LOW", status="COMPLETED")
        s = selectors.owner_dashboard(self.owner)["stats"]
        self.assertEqual(s["maintenance_open"], 1)
        self.assertEqual(s["maintenance_urgent"], 1)

    def test_revenue_trend_shape_and_bucketing(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=today.month, year=today.year,
            due_date=today, amount=Decimal("700"), late_fee=Decimal("50"),
            status="PAID", payment_date=today)
        chart = selectors.owner_dashboard(self.owner)["chart_revenue"]
        self.assertEqual(len(chart["labels"]), 6)
        self.assertEqual(len(chart["values"]), 6)
        # Current month is the last bucket; amount + late_fee.
        self.assertEqual(chart["values"][-1], 750.0)

    def test_lease_expiries_window(self):
        self.lease.end_date = timezone.localdate() + timedelta(days=10)
        self.lease.save()
        data = selectors.owner_dashboard(self.owner)
        self.assertIn(self.lease, data["lease_expiries"])
        # Push it well beyond the 90-day window.
        self.lease.end_date = timezone.localdate() + timedelta(days=200)
        self.lease.save()
        self.assertNotIn(self.lease, selectors.owner_dashboard(self.owner)["lease_expiries"])

    def test_dashboard_page_renders(self):
        self.client.login(username="own@x.com", password="Pass!2345")
        r = self.client.get(reverse("dashboard:owner"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Owner Dashboard")
        self.assertContains(r, "revenueChart")


class AdminSelectorTests(TestCase):
    def test_platform_wide_counts(self):
        admin = User.objects.create_user("a", "a@x.com", "Pass!2345", role="ADMIN")
        o1 = User.objects.create_user("o1", "o1@x.com", "p", role="OWNER")
        o2 = User.objects.create_user("o2", "o2@x.com", "p", role="OWNER")
        build_world(o1)
        build_world(o2)
        s = selectors.admin_dashboard(admin)["stats"]
        self.assertEqual(s["total_owners"], 2)
        self.assertEqual(s["total_tenants"], 2)   # one per world
        self.assertEqual(s["total_properties"], 2)
        self.assertEqual(s["occupied_units"], 2)

    def test_admin_page_renders(self):
        User.objects.create_user("a", "a@x.com", "Pass!2345", role="ADMIN")
        self.client.login(username="a@x.com", password="Pass!2345")
        r = self.client.get(reverse("dashboard:admin"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Admin Dashboard")


class TenantSelectorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner, "1200")

    def test_tenant_sees_their_lease_and_dues(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=1, year=2030,
            due_date=today + timedelta(days=5), amount=Decimal("1200"), status="PENDING")
        data = selectors.tenant_dashboard(self.tenant.user)
        self.assertEqual(data["lease"], self.lease)
        self.assertEqual(data["stats"]["amount_due"], Decimal("1200"))
        self.assertIsNone(data["stats"]["overdue"])

    def test_overdue_surfaces(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=2, year=2020,
            due_date=today - timedelta(days=3), amount=Decimal("1200"), status="PENDING")
        data = selectors.tenant_dashboard(self.tenant.user)
        self.assertIsNotNone(data["stats"]["overdue"])

    def test_tenant_without_profile_gets_empty_state(self):
        """A self-registered tenant has no Tenant profile — must not crash."""
        u = User.objects.create_user("solo@x.com", "solo@x.com", "Pass!2345", role="TENANT")
        data = selectors.tenant_dashboard(u)
        self.assertIsNone(data["profile"])
        self.assertIsNone(data["lease"])
        self.client.login(username="solo@x.com", password="Pass!2345")
        r = self.client.get(reverse("dashboard:tenant"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No active lease")

    def test_tenant_page_renders(self):
        self.tenant.user.set_password("Pass!2345")
        self.tenant.user.save()
        self.client.login(username=self.tenant.user.email, password="Pass!2345")
        r = self.client.get(reverse("dashboard:tenant"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Your Lease")
