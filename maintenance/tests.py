"""Tests for maintenance: role scoping, workflow, unit choices, completion."""

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
from maintenance.models import MaintenanceRequest

_seq = count(1)


def build_leased_unit(owner, tenant_user=None):
    """Property + unit + tenant with an active lease on it."""
    n = next(_seq)
    prop = Property.objects.create(owner=owner, title=f"P{n}", property_type="RESIDENTIAL",
        status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")
    unit = Unit.objects.create(property=prop, unit_number=f"U{n}", rent_amount=Decimal("1500"))
    if tenant_user is None:
        tenant_user = User.objects.create_user(f"t{n}@x.com", f"t{n}@x.com", "Pass!2345", role="TENANT")
    tenant = Tenant.objects.create(user=tenant_user, created_by=owner)
    today = timezone.localdate()
    Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
        end_date=today + timedelta(days=365), monthly_rent=Decimal("1500"), status="ACTIVE")
    return unit, tenant


class MaintenanceModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.unit, cls.tenant = build_leased_unit(cls.owner)

    def test_completed_stamps_date(self):
        r = MaintenanceRequest.objects.create(unit=self.unit, tenant=self.tenant,
            title="Leaky AC", status="OPEN")
        self.assertIsNone(r.completed_date)
        r.status = "COMPLETED"
        r.save()
        self.assertEqual(r.completed_date, timezone.localdate())

    def test_reopening_clears_completed_date(self):
        r = MaintenanceRequest.objects.create(unit=self.unit, title="X", status="COMPLETED")
        self.assertIsNotNone(r.completed_date)
        r.status = "IN_PROGRESS"
        r.save()
        self.assertIsNone(r.completed_date)

    def test_open_queryset_excludes_completed(self):
        MaintenanceRequest.objects.create(unit=self.unit, title="A", status="OPEN")
        MaintenanceRequest.objects.create(unit=self.unit, title="B", status="COMPLETED")
        self.assertEqual(MaintenanceRequest.objects.open().count(), 1)


class MaintenanceRoleScopingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.other_owner = User.objects.create_user("own2", "own2@x.com", "Pass!2345", role="OWNER")
        cls.tenant_user = User.objects.create_user("ten@x.com", "ten@x.com", "Pass!2345", role="TENANT")
        cls.unit, cls.tenant = build_leased_unit(cls.owner, cls.tenant_user)
        cls.other_unit, _ = build_leased_unit(cls.other_owner)

        cls.req = MaintenanceRequest.objects.create(unit=cls.unit, tenant=cls.tenant,
            title="Leaky AC", priority="HIGH", created_by=cls.tenant_user)
        cls.other_req = MaintenanceRequest.objects.create(unit=cls.other_unit, title="Other")

    def test_tenant_can_access_and_sees_only_own(self):
        self.client.login(username="ten@x.com", password="Pass!2345")
        r = self.client.get(reverse("maintenance:list"))
        self.assertEqual(r.status_code, 200)  # tenants are NOT 403 here
        self.assertEqual(list(r.context["object_list"]), [self.req])
        self.assertEqual(self.client.get(
            reverse("maintenance:detail", args=[self.other_req.pk])).status_code, 404)

    def test_owner_sees_only_their_properties(self):
        self.client.login(username="own@x.com", password="Pass!2345")
        r = self.client.get(reverse("maintenance:list"))
        self.assertEqual(list(r.context["object_list"]), [self.req])

    def test_tenant_cannot_manage(self):
        self.client.login(username="ten@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(
            reverse("maintenance:manage", args=[self.req.pk])).status_code, 403)

    def test_tenant_unit_choices_limited_to_leased(self):
        self.client.login(username="ten@x.com", password="Pass!2345")
        r = self.client.get(reverse("maintenance:create"))
        self.assertEqual(list(r.context["form"].fields["unit"].queryset), [self.unit])


class MaintenanceWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.tenant_user = User.objects.create_user("ten@x.com", "ten@x.com", "Pass!2345", role="TENANT")
        cls.unit, cls.tenant = build_leased_unit(cls.owner, cls.tenant_user)

    def test_tenant_create_sets_tenant_and_creator(self):
        self.client.login(username="ten@x.com", password="Pass!2345")
        self.client.post(reverse("maintenance:create"), {
            "unit": self.unit.pk, "title": "No hot water",
            "description": "Since Monday", "priority": "HIGH"})
        r = MaintenanceRequest.objects.get(title="No hot water")
        self.assertEqual(r.tenant, self.tenant)
        self.assertEqual(r.created_by, self.tenant_user)
        self.assertEqual(r.status, "OPEN")

    def test_owner_create_links_current_tenant(self):
        self.client.login(username="own@x.com", password="Pass!2345")
        self.client.post(reverse("maintenance:create"), {
            "unit": self.unit.pk, "title": "Repaint", "priority": "LOW"})
        r = MaintenanceRequest.objects.get(title="Repaint")
        # Auto-attributed to the unit's active-lease tenant.
        self.assertEqual(r.tenant, self.tenant)

    def test_assigning_moves_open_to_assigned(self):
        req = MaintenanceRequest.objects.create(unit=self.unit, title="X", status="OPEN")
        self.client.login(username="own@x.com", password="Pass!2345")
        self.client.post(reverse("maintenance:manage", args=[req.pk]), {
            "status": "OPEN", "assigned_to": self.owner.pk, "estimated_cost": "500"})
        req.refresh_from_db()
        self.assertEqual(req.status, "ASSIGNED")
        self.assertEqual(req.assigned_to, self.owner)
        self.assertEqual(req.estimated_cost, Decimal("500"))

    def test_open_tickets_stat_on_properties(self):
        MaintenanceRequest.objects.create(unit=self.unit, title="A", status="OPEN", priority="HIGH")
        MaintenanceRequest.objects.create(unit=self.unit, title="B", status="COMPLETED")
        self.client.login(username="own@x.com", password="Pass!2345")
        r = self.client.get(reverse("properties:list"))
        self.assertEqual(r.context["stats"]["open_tickets"], 1)
        self.assertEqual(r.context["stats"]["high_priority_tickets"], 1)
