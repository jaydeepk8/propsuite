"""Tests for the DRF API: JWT auth, CRUD, scoping, permissions, actions."""

from datetime import timedelta
from decimal import Decimal
from itertools import count

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from properties.models import Property, Unit
from tenants.models import Tenant
from leases.models import Lease
from payments.models import RentPayment
from maintenance.models import MaintenanceRequest
from notifications.models import Notification

_seq = count(1)


def make_owner(email="own@x.com"):
    return User.objects.create_user(email.split("@")[0], email, "Pass!2345", role="OWNER")


def make_property(owner, **over):
    n = next(_seq)
    data = dict(title=f"P{n}", property_type="RESIDENTIAL", status="ACTIVE",
                address="x", city="Austin", state="TX", country="USA", pincode="1")
    data.update(over)
    return Property.objects.create(owner=owner, **data)


class JWTAuthTests(APITestCase):
    def setUp(self):
        self.owner = make_owner()

    def test_obtain_token_with_username(self):
        r = self.client.post("/api/auth/token/",
                             {"username": "own", "password": "Pass!2345"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertIn("refresh", r.data)

    def test_obtain_token_with_email(self):
        # Our EmailOrUsernameBackend lets the username field carry an email.
        r = self.client.post("/api/auth/token/",
                             {"username": "own@x.com", "password": "Pass!2345"})
        self.assertEqual(r.status_code, 200)

    def test_bad_credentials_rejected(self):
        r = self.client.post("/api/auth/token/",
                             {"username": "own", "password": "wrong"})
        self.assertEqual(r.status_code, 401)

    def test_protected_endpoint_requires_token(self):
        self.assertEqual(self.client.get("/api/properties/").status_code, 401)

    def test_token_grants_access(self):
        token = self.client.post("/api/auth/token/",
                                 {"username": "own", "password": "Pass!2345"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(self.client.get("/api/properties/").status_code, 200)

    def test_me_endpoint(self):
        token = self.client.post("/api/auth/token/",
                                 {"username": "own", "password": "Pass!2345"}).data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        r = self.client.get("/api/me/")
        self.assertEqual(r.data["role"], "OWNER")
        self.assertEqual(r.data["email"], "own@x.com")


class PropertyAPITests(APITestCase):
    def setUp(self):
        self.owner = make_owner("own@x.com")
        self.other = make_owner("o2@x.com")
        self.client.force_authenticate(self.owner)

    def test_create_sets_owner(self):
        r = self.client.post("/api/properties/", {
            "title": "Skyline", "property_type": "RESIDENTIAL", "status": "ACTIVE",
            "address": "1 St", "city": "Chicago", "state": "IL",
            "country": "USA", "pincode": "60601", "total_units": 5})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Property.objects.get(title="Skyline").owner, self.owner)

    def test_list_scoped_to_owner(self):
        make_property(self.owner, title="Mine")
        make_property(self.other, title="Theirs")
        r = self.client.get("/api/properties/")
        titles = [p["title"] for p in r.data["results"]]
        self.assertIn("Mine", titles)
        self.assertNotIn("Theirs", titles)

    def test_cannot_retrieve_others_property(self):
        p = make_property(self.other)
        self.assertEqual(self.client.get(f"/api/properties/{p.pk}/").status_code, 404)

    def test_search_and_filter(self):
        make_property(self.owner, title="Skyline", city="Chicago")
        make_property(self.owner, title="Beacon", city="Denver", property_type="COMMERCIAL")
        self.assertEqual(len(self.client.get("/api/properties/?search=skyline").data["results"]), 1)
        self.assertEqual(len(self.client.get("/api/properties/?property_type=COMMERCIAL").data["results"]), 1)

    def test_tenant_cannot_use_property_api(self):
        tu = User.objects.create_user("t@x.com", "t@x.com", "Pass!2345", role="TENANT")
        self.client.force_authenticate(tu)
        self.assertEqual(self.client.get("/api/properties/").status_code, 403)


class PaymentAndMaintenanceAPITests(APITestCase):
    def setUp(self):
        self.owner = make_owner()
        self.prop = make_property(self.owner)
        self.unit = Unit.objects.create(property=self.prop, unit_number="101",
                                        rent_amount=Decimal("1500"))
        self.tenant_user = User.objects.create_user("ten@x.com", "ten@x.com", "Pass!2345", role="TENANT")
        self.tenant = Tenant.objects.create(user=self.tenant_user, created_by=self.owner)
        today = timezone.localdate()
        self.lease = Lease.objects.create(tenant=self.tenant, unit=self.unit,
            start_date=today, end_date=today + timedelta(days=365),
            monthly_rent=Decimal("1500"), status="ACTIVE")

    def test_mark_paid_action(self):
        self.client.force_authenticate(self.owner)
        p = RentPayment.objects.create(lease=self.lease, month=7, year=2026,
            due_date=timezone.localdate(), amount=Decimal("1500"), status="PENDING")
        r = self.client.post(f"/api/payments/{p.pk}/mark_paid/",
                             {"payment_method": "UPI"})
        self.assertEqual(r.status_code, 200)
        p.refresh_from_db()
        self.assertEqual(p.status, "PAID")
        self.assertEqual(r.data["effective_status"], "PAID")

    def test_tenant_can_create_maintenance_for_leased_unit(self):
        self.client.force_authenticate(self.tenant_user)
        r = self.client.post("/api/maintenance/", {
            "unit": self.unit.pk, "title": "Leaky tap", "priority": "HIGH"})
        self.assertEqual(r.status_code, 201)
        req = MaintenanceRequest.objects.get(title="Leaky tap")
        self.assertEqual(req.tenant, self.tenant)
        self.assertEqual(req.created_by, self.tenant_user)

    def test_tenant_cannot_raise_for_unleased_unit(self):
        other_unit = Unit.objects.create(property=self.prop, unit_number="999",
                                         rent_amount=Decimal("1"))
        self.client.force_authenticate(self.tenant_user)
        r = self.client.post("/api/maintenance/", {
            "unit": other_unit.pk, "title": "Nope", "priority": "LOW"})
        self.assertEqual(r.status_code, 400)

    def test_tenant_sees_only_own_maintenance(self):
        MaintenanceRequest.objects.create(unit=self.unit, tenant=self.tenant, title="Mine")
        # A request the tenant isn't tied to.
        other_owner = make_owner("o3@x.com")
        op = make_property(other_owner)
        ou = Unit.objects.create(property=op, unit_number="1", rent_amount=Decimal("1"))
        MaintenanceRequest.objects.create(unit=ou, title="Theirs")
        self.client.force_authenticate(self.tenant_user)
        r = self.client.get("/api/maintenance/")
        titles = [x["title"] for x in r.data["results"]]
        self.assertEqual(titles, ["Mine"])


class NotificationAPITests(APITestCase):
    def setUp(self):
        self.owner = make_owner()
        self.client.force_authenticate(self.owner)

    def test_unread_count_and_read_all(self):
        Notification.objects.create(user=self.owner, title="A")
        Notification.objects.create(user=self.owner, title="B")
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["unread"], 2)
        r = self.client.post("/api/notifications/read_all/")
        self.assertEqual(r.data["marked_read"], 2)
        self.assertEqual(self.client.get("/api/notifications/unread_count/").data["unread"], 0)

    def test_read_single(self):
        n = Notification.objects.create(user=self.owner, title="A")
        self.client.post(f"/api/notifications/{n.pk}/read/")
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_notifications_are_read_only(self):
        # No create endpoint on a ReadOnlyModelViewSet.
        r = self.client.post("/api/notifications/", {"title": "X"})
        self.assertEqual(r.status_code, 405)
