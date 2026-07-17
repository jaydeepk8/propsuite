"""Tests for notifications: signal triggers, inbox views, reminder commands."""

from datetime import timedelta
from decimal import Decimal
from itertools import count

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Property, Unit
from tenants.models import Tenant
from leases.models import Lease
from payments.models import RentPayment
from maintenance.models import MaintenanceRequest
from inspections.models import Inspection
from notifications.models import Notification

_seq = count(1)


def build_world(owner):
    """Owner -> property -> unit -> tenant -> active lease."""
    n = next(_seq)
    prop = Property.objects.create(owner=owner, title=f"P{n}", property_type="RESIDENTIAL",
        status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")
    unit = Unit.objects.create(property=prop, unit_number=f"U{n}", rent_amount=Decimal("1500"))
    tu = User.objects.create_user(f"t{n}@x.com", f"t{n}@x.com", "Pass!2345", role="TENANT")
    tenant = Tenant.objects.create(user=tu, created_by=owner)
    today = timezone.localdate()
    lease = Lease.objects.create(tenant=tenant, unit=unit, start_date=today,
        end_date=today + timedelta(days=365), monthly_rent=Decimal("1500"), status="ACTIVE")
    return prop, unit, tenant, lease


class PaymentNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner)

    def test_new_pending_payment_notifies_tenant(self):
        RentPayment.objects.create(lease=self.lease, month=7, year=2026,
            due_date=timezone.localdate(), amount=Decimal("1500"), status="PENDING")
        n = Notification.objects.get(user=self.tenant.user, kind="RENT_DUE")
        self.assertIn("Rent due", n.title)
        self.assertFalse(n.is_read)

    def test_payment_becoming_paid_notifies_owner(self):
        p = RentPayment.objects.create(lease=self.lease, month=8, year=2026,
            due_date=timezone.localdate(), amount=Decimal("1500"), status="PENDING")
        self.assertFalse(Notification.objects.filter(user=self.owner, kind="PAYMENT_RECEIVED").exists())
        p.mark_paid(method="UPI")
        n = Notification.objects.get(user=self.owner, kind="PAYMENT_RECEIVED")
        self.assertIn("Payment received", n.title)

    def test_paid_twice_does_not_double_notify(self):
        p = RentPayment.objects.create(lease=self.lease, month=9, year=2026,
            due_date=timezone.localdate(), amount=Decimal("1500"), status="PENDING")
        p.mark_paid(method="CASH")
        p.save()  # saving again while already PAID
        self.assertEqual(
            Notification.objects.filter(user=self.owner, kind="PAYMENT_RECEIVED").count(), 1)


class MaintenanceNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner)

    def test_new_request_notifies_owner(self):
        MaintenanceRequest.objects.create(unit=self.unit, tenant=self.tenant,
            title="Leaky AC", priority="HIGH")
        n = Notification.objects.get(user=self.owner, kind="MAINTENANCE")
        self.assertIn("New maintenance request", n.title)

    def test_assignment_notifies_assignee_and_tenant(self):
        r = MaintenanceRequest.objects.create(unit=self.unit, tenant=self.tenant, title="X")
        Notification.objects.all().delete()  # ignore the creation notice
        r.assigned_to = self.owner
        r.save()
        self.assertTrue(Notification.objects.filter(
            user=self.owner, title__startswith="Maintenance assigned").exists())
        self.assertTrue(Notification.objects.filter(
            user=self.tenant.user, title__startswith="Your request is being handled").exists())

    def test_resaving_same_assignee_does_not_renotify(self):
        r = MaintenanceRequest.objects.create(unit=self.unit, tenant=self.tenant, title="X")
        r.assigned_to = self.owner
        r.save()
        before = Notification.objects.filter(title__startswith="Maintenance assigned").count()
        r.save()
        self.assertEqual(
            Notification.objects.filter(title__startswith="Maintenance assigned").count(), before)


class InspectionNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner)

    def test_scheduling_notifies_owner_and_sitting_tenant(self):
        Inspection.objects.create(property=self.prop, unit=self.unit,
            inspector=self.owner, inspection_date=timezone.localdate())
        self.assertTrue(Notification.objects.filter(user=self.owner, kind="INSPECTION").exists())
        self.assertTrue(Notification.objects.filter(user=self.tenant.user, kind="INSPECTION").exists())

    def test_owner_notified_once_when_also_inspector(self):
        # owner is both property owner and inspector -> notify_many dedupes
        Inspection.objects.create(property=self.prop, inspector=self.owner,
            inspection_date=timezone.localdate())
        self.assertEqual(
            Notification.objects.filter(user=self.owner, kind="INSPECTION").count(), 1)


class NotificationViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.other = User.objects.create_user("o2", "o2@x.com", "Pass!2345", role="OWNER")

    def setUp(self):
        self.client.login(username="own@x.com", password="Pass!2345")

    def test_inbox_shows_only_own(self):
        mine = Notification.objects.create(user=self.owner, title="Mine")
        Notification.objects.create(user=self.other, title="Theirs")
        r = self.client.get(reverse("notifications:list"))
        self.assertEqual(list(r.context["object_list"]), [mine])
        self.assertEqual(r.context["unread_total"], 1)

    def test_read_marks_and_redirects_to_target(self):
        n = Notification.objects.create(user=self.owner, title="Go", url="/properties/")
        r = self.client.get(reverse("notifications:read", args=[n.pk]))
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertRedirects(r, "/properties/")

    def test_cannot_read_someone_elses(self):
        n = Notification.objects.create(user=self.other, title="Nope")
        self.assertEqual(self.client.get(reverse("notifications:read", args=[n.pk])).status_code, 404)

    def test_mark_all_read(self):
        Notification.objects.create(user=self.owner, title="A")
        Notification.objects.create(user=self.owner, title="B")
        self.client.post(reverse("notifications:read_all"))
        self.assertEqual(Notification.objects.for_user(self.owner).unread().count(), 0)

    def test_unread_badge_count_in_context(self):
        Notification.objects.create(user=self.owner, title="A")
        r = self.client.get(reverse("properties:list"))
        self.assertEqual(r.context["unread_notification_count"], 1)


class ReminderCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner)

    def test_rent_reminders_notify_and_email(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=1, year=2030,
            due_date=today + timedelta(days=2), amount=Decimal("1500"), status="PENDING")
        Notification.objects.all().delete()
        mail.outbox = []
        call_command("send_rent_reminders", "--days", "3")
        self.assertTrue(Notification.objects.filter(
            user=self.tenant.user, title__startswith="Rent reminder").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_rent_reminders_skip_outside_window(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=2, year=2030,
            due_date=today + timedelta(days=30), amount=Decimal("1500"), status="PENDING")
        Notification.objects.all().delete()
        call_command("send_rent_reminders", "--days", "3")
        self.assertFalse(Notification.objects.filter(title__startswith="Rent reminder").exists())

    def test_lease_expiry_reminders(self):
        today = timezone.localdate()
        self.lease.end_date = today + timedelta(days=10)
        self.lease.save()
        Notification.objects.all().delete()
        mail.outbox = []
        call_command("send_lease_expiry_reminders", "--days", "30")
        self.assertTrue(Notification.objects.filter(
            user=self.tenant.user, kind="LEASE_EXPIRY").exists())
        self.assertTrue(Notification.objects.filter(
            user=self.owner, kind="LEASE_EXPIRY").exists())
        self.assertEqual(len(mail.outbox), 1)  # tenant emailed, owner in-app only

    def test_dry_run_creates_nothing(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=3, year=2030,
            due_date=today + timedelta(days=1), amount=Decimal("1500"), status="PENDING")
        Notification.objects.all().delete()
        call_command("send_rent_reminders", "--days", "3", "--dry-run")
        self.assertFalse(Notification.objects.filter(title__startswith="Rent reminder").exists())
