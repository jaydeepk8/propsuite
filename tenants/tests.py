"""Tests for tenant onboarding and access scoping."""

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from tenants.models import Tenant


class TenantOnboardingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")

    def setUp(self):
        self.client.login(username="own@x.com", password="Pass!2345")

    def test_create_provisions_tenant_user(self):
        self.client.post(reverse("tenants:create"), {
            "first_name": "Sara", "last_name": "M", "email": "sara@x.com",
            "phone": "+919812345678", "emergency_contact": "", "occupation": "Nurse",
            "aadhaar_number": "123412341234"})
        t = Tenant.objects.get(user__email="sara@x.com")
        self.assertEqual(t.user.role, "TENANT")
        self.assertEqual(t.created_by, self.owner)
        self.assertFalse(t.user.has_usable_password())  # set via reset
        self.assertEqual(t.masked_aadhaar, "XXXX XXXX 1234")

    def test_duplicate_email_rejected(self):
        User.objects.create_user("dupe", "dupe@x.com", "p", role="TENANT")
        r = self.client.post(reverse("tenants:create"), {
            "first_name": "A", "last_name": "B", "email": "dupe@x.com",
            "phone": "", "emergency_contact": "", "occupation": ""})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "already exists")

    def test_owner_cannot_see_others_tenant(self):
        other = User.objects.create_user("o2", "o2@x.com", "p", role="OWNER")
        u = User.objects.create_user("t2", "t2@x.com", "p", role="TENANT")
        t = Tenant.objects.create(user=u, created_by=other)
        self.assertEqual(self.client.get(reverse("tenants:detail", args=[t.pk])).status_code, 404)
