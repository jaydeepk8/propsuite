"""Tests for the properties module: models, CRUD, access control, filtering."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Property, Unit


class PropertyModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop = Property.objects.create(
            owner=cls.owner, title="Skyline", property_type="RESIDENTIAL",
            status="ACTIVE", address="1 St", city="Chicago", state="IL",
            country="USA", pincode="60601",
        )
        Unit.objects.create(property=cls.prop, unit_number="101",
                            rent_amount=Decimal("1500"), status="OCCUPIED")
        Unit.objects.create(property=cls.prop, unit_number="102",
                            rent_amount=Decimal("1500"), status="OCCUPIED")
        Unit.objects.create(property=cls.prop, unit_number="103",
                            rent_amount=Decimal("1200"), status="AVAILABLE")

    def test_unit_rollups(self):
        self.assertEqual(self.prop.units_count, 3)
        self.assertEqual(self.prop.occupied_count, 2)
        self.assertEqual(self.prop.vacant_count, 1)
        self.assertEqual(self.prop.occupancy_rate, 66.7)
        self.assertEqual(self.prop.monthly_income, Decimal("3000"))

    def test_unit_number_unique_per_property(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Unit.objects.create(property=self.prop, unit_number="101",
                                rent_amount=Decimal("1"))


class PropertyViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("owner_a", "a@x.com", "Pass!2345", role="OWNER")
        cls.b = User.objects.create_user("owner_b", "b@x.com", "Pass!2345", role="OWNER")

    def setUp(self):
        self.client.login(username="a@x.com", password="Pass!2345")

    def _create_payload(self, **over):
        data = dict(title="Skyline Lofts", property_type="RESIDENTIAL",
                    status="ACTIVE", description="Nice", address="1 Main St",
                    city="Chicago", state="IL", country="USA", pincode="60601",
                    total_units=10)
        data.update(over)
        return data

    def test_create_assigns_owner(self):
        self.client.post(reverse("properties:create"), self._create_payload())
        p = Property.objects.get(title="Skyline Lofts")
        self.assertEqual(p.owner, self.a)

    def test_list_stats_and_render(self):
        p = Property.objects.create(owner=self.a, title="Skyline Lofts",
            property_type="RESIDENTIAL", status="ACTIVE", address="1 Main St",
            city="Chicago", state="IL", country="USA", pincode="60601")
        Unit.objects.create(property=p, unit_number="1", rent_amount=Decimal("1500"), status="OCCUPIED")
        Unit.objects.create(property=p, unit_number="2", rent_amount=Decimal("1200"), status="AVAILABLE")
        r = self.client.get(reverse("properties:list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["stats"]["total_units"], 2)
        self.assertEqual(r.context["stats"]["occupancy_rate"], 50.0)
        self.assertEqual(r.context["stats"]["gross_income"], Decimal("1500"))
        self.assertContains(r, "Skyline Lofts")

    def test_ownership_isolation(self):
        p = Property.objects.create(owner=self.a, title="A's", property_type="RESIDENTIAL",
            status="ACTIVE", address="x", city="Chicago", state="IL", country="USA", pincode="1")
        self.client.logout()
        self.client.login(username="b@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(reverse("properties:detail", args=[p.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("properties:update", args=[p.pk]), {}).status_code, 404)

    def test_search_and_filter(self):
        Property.objects.create(owner=self.a, title="Skyline", property_type="RESIDENTIAL",
            status="ACTIVE", address="x", city="Chicago", state="IL", country="USA", pincode="1")
        Property.objects.create(owner=self.a, title="Beacon", property_type="COMMERCIAL",
            status="ACTIVE", address="x", city="Denver", state="CO", country="USA", pincode="1")
        self.assertEqual(self.client.get(reverse("properties:list") + "?q=skyline").context["object_list"].count(), 1)
        self.assertEqual(self.client.get(reverse("properties:list") + "?q=zzz").context["object_list"].count(), 0)
        self.assertEqual(self.client.get(reverse("properties:list") + "?city=Denver").context["object_list"].count(), 1)
        self.assertEqual(self.client.get(reverse("properties:list") + "?property_type=COMMERCIAL").context["object_list"].count(), 1)

    def test_pagination(self):
        for i in range(8):
            Property.objects.create(owner=self.a, title=f"P{i}", property_type="RESIDENTIAL",
                status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")
        r = self.client.get(reverse("properties:list"))
        self.assertTrue(r.context["is_paginated"])
        self.assertEqual(len(r.context["object_list"]), 6)
        self.assertEqual(len(self.client.get(reverse("properties:list") + "?page=2").context["object_list"]), 2)

    def test_update_and_delete(self):
        p = Property.objects.create(owner=self.a, title="Old", property_type="RESIDENTIAL",
            status="ACTIVE", address="x", city="Chicago", state="IL", country="USA", pincode="1")
        self.client.post(reverse("properties:update", args=[p.pk]), self._create_payload(title="New", status="PENDING"))
        p.refresh_from_db()
        self.assertEqual((p.title, p.status), ("New", "PENDING"))
        self.client.post(reverse("properties:delete", args=[p.pk]))
        self.assertFalse(Property.objects.filter(pk=p.pk).exists())


class UnitViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = User.objects.create_user("owner_a", "a@x.com", "Pass!2345", role="OWNER")
        cls.prop = Property.objects.create(owner=cls.a, title="P", property_type="RESIDENTIAL",
            status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")

    def setUp(self):
        self.client.login(username="a@x.com", password="Pass!2345")

    def test_unit_create_and_delete(self):
        self.client.post(reverse("properties:unit_create", args=[self.prop.pk]), dict(
            unit_number="201", floor=2, bedrooms=2, bathrooms=1,
            rent_amount="1800", security_deposit="3600", status="AVAILABLE"))
        u = Unit.objects.get(unit_number="201")
        self.assertEqual(u.property, self.prop)
        self.client.post(reverse("properties:unit_delete", args=[u.pk]))
        self.assertFalse(Unit.objects.filter(pk=u.pk).exists())

    def test_tenant_forbidden(self):
        User.objects.create_user("t", "t@x.com", "Pass!2345", role="TENANT")
        self.client.logout()
        self.client.login(username="t@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(reverse("properties:list")).status_code, 403)
