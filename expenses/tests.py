"""Tests for expenses and the analytics page."""

from datetime import timedelta
from decimal import Decimal
from itertools import count

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Property, Unit
from expenses.models import Expense

_seq = count(1)


def make_property(owner):
    n = next(_seq)
    return Property.objects.create(owner=owner, title=f"P{n}", property_type="RESIDENTIAL",
        status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")


class ExpenseViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.other = User.objects.create_user("o2", "o2@x.com", "Pass!2345", role="OWNER")
        cls.prop = make_property(cls.owner)

    def setUp(self):
        self.client.login(username="own@x.com", password="Pass!2345")

    def test_create_expense(self):
        self.client.post(reverse("expenses:create"), {
            "property": self.prop.pk, "category": "UTILITIES", "title": "Electricity",
            "amount": "2500", "date": timezone.localdate(), "vendor": "PowerCo"})
        e = Expense.objects.get(title="Electricity")
        self.assertEqual(e.created_by, self.owner)
        self.assertEqual(e.amount, Decimal("2500"))

    def test_list_totals_and_by_category(self):
        Expense.objects.create(property=self.prop, category="UTILITIES", title="A",
            amount=Decimal("1000"), date=timezone.localdate())
        Expense.objects.create(property=self.prop, category="TAX", title="B",
            amount=Decimal("3000"), date=timezone.localdate())
        r = self.client.get(reverse("expenses:list"))
        self.assertEqual(r.context["total"], Decimal("4000"))
        self.assertEqual(dict(r.context["by_category"])["Property Tax"], Decimal("3000"))

    def test_form_property_scoped_to_owner(self):
        make_property(self.other)
        r = self.client.get(reverse("expenses:create"))
        self.assertEqual(list(r.context["form"].fields["property"].queryset), [self.prop])

    def test_ownership_isolation(self):
        other_prop = make_property(self.other)
        e = Expense.objects.create(property=other_prop, category="OTHER", title="X",
            amount=Decimal("1"), date=timezone.localdate())
        self.assertEqual(self.client.get(reverse("expenses:update", args=[e.pk])).status_code, 404)

    def test_category_filter(self):
        Expense.objects.create(property=self.prop, category="UTILITIES", title="A",
            amount=Decimal("1000"), date=timezone.localdate())
        Expense.objects.create(property=self.prop, category="TAX", title="B",
            amount=Decimal("3000"), date=timezone.localdate())
        r = self.client.get(reverse("expenses:list") + "?category=TAX")
        self.assertEqual(len(r.context["object_list"]), 1)

    def test_tenant_forbidden(self):
        User.objects.create_user("t@x.com", "t@x.com", "Pass!2345", role="TENANT")
        self.client.logout()
        self.client.login(username="t@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(reverse("expenses:list")).status_code, 403)


class AnalyticsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.prop = make_property(cls.owner)
        Unit.objects.create(property=cls.prop, unit_number="1", rent_amount=Decimal("1000"), status="OCCUPIED")
        Unit.objects.create(property=cls.prop, unit_number="2", rent_amount=Decimal("1000"), status="AVAILABLE")
        Expense.objects.create(property=cls.prop, category="TAX", title="Tax",
            amount=Decimal("5000"), date=timezone.localdate())

    def test_analytics_renders_with_data(self):
        self.client.login(username="own@x.com", password="Pass!2345")
        r = self.client.get(reverse("dashboard:analytics"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Occupancy Analytics")
        self.assertEqual(r.context["totals"]["expense"], Decimal("5000"))
        self.assertEqual(r.context["breakdown"]["occupied"], 1)
        self.assertEqual(len(r.context["per_property"]), 1)

    def test_tenant_cannot_view_analytics(self):
        User.objects.create_user("t@x.com", "t@x.com", "Pass!2345", role="TENANT")
        self.client.login(username="t@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(reverse("dashboard:analytics")).status_code, 403)
