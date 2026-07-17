"""Tests for inspections: scoping, validation, report upload, status."""

import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from itertools import count

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from properties.models import Property, Unit
from inspections.models import Inspection

_seq = count(1)
_TMP_MEDIA = tempfile.mkdtemp()


def build_property(owner):
    n = next(_seq)
    prop = Property.objects.create(owner=owner, title=f"P{n}", property_type="RESIDENTIAL",
        status="ACTIVE", address="x", city="Austin", state="TX", country="USA", pincode="1")
    unit = Unit.objects.create(property=prop, unit_number=f"U{n}", rent_amount=Decimal("1500"))
    return prop, unit


class InspectionModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit = build_property(cls.owner)

    def test_overdue_and_upcoming(self):
        today = timezone.localdate()
        past = Inspection.objects.create(property=self.prop,
            inspection_date=today - timedelta(days=1), status="SCHEDULED")
        future = Inspection.objects.create(property=self.prop,
            inspection_date=today + timedelta(days=7), status="SCHEDULED")
        self.assertTrue(past.is_overdue)
        self.assertFalse(past.is_upcoming)
        self.assertTrue(future.is_upcoming)
        self.assertFalse(future.is_overdue)
        self.assertEqual(Inspection.objects.upcoming().count(), 1)

    def test_completed_not_overdue(self):
        today = timezone.localdate()
        done = Inspection.objects.create(property=self.prop,
            inspection_date=today - timedelta(days=10), status="COMPLETED")
        self.assertFalse(done.is_overdue)

    def test_unit_must_belong_to_property(self):
        from django.core.exceptions import ValidationError
        other_prop, other_unit = build_property(self.owner)
        insp = Inspection(property=self.prop, unit=other_unit,
                          inspection_date=timezone.localdate())
        with self.assertRaises(ValidationError):
            insp.full_clean()


@override_settings(MEDIA_ROOT=_TMP_MEDIA)
class InspectionViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.other = User.objects.create_user("own2", "own2@x.com", "Pass!2345", role="OWNER")
        cls.prop, cls.unit = build_property(cls.owner)
        cls.other_prop, cls.other_unit = build_property(cls.other)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client.login(username="own@x.com", password="Pass!2345")

    def test_schedule_inspection(self):
        today = timezone.localdate()
        self.client.post(reverse("inspections:create"), {
            "property": self.prop.pk, "unit": self.unit.pk,
            "inspector": self.owner.pk, "inspection_date": today + timedelta(days=3),
            "status": "SCHEDULED", "notes": "Annual check"})
        insp = Inspection.objects.get(notes="Annual check")
        self.assertEqual(insp.property, self.prop)
        self.assertEqual(insp.created_by, self.owner)
        self.assertEqual(insp.status, "SCHEDULED")

    def test_form_rejects_unit_from_other_property(self):
        today = timezone.localdate()
        r = self.client.post(reverse("inspections:create"), {
            "property": self.prop.pk, "unit": self.other_unit.pk,
            "inspection_date": today, "status": "SCHEDULED"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Inspection.objects.filter(property=self.prop).exists())

    def test_report_upload_marks_completed(self):
        insp = Inspection.objects.create(property=self.prop,
            inspection_date=timezone.localdate(), status="SCHEDULED")
        pdf = SimpleUploadedFile("report.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        self.client.post(reverse("inspections:upload_report", args=[insp.pk]),
                         {"report": pdf, "notes": "All good"})
        insp.refresh_from_db()
        self.assertTrue(insp.has_report)
        self.assertEqual(insp.status, "COMPLETED")
        self.assertEqual(insp.notes, "All good")

    def test_bad_file_extension_rejected(self):
        insp = Inspection.objects.create(property=self.prop,
            inspection_date=timezone.localdate(), status="SCHEDULED")
        bad = SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")
        r = self.client.post(reverse("inspections:upload_report", args=[insp.pk]),
                             {"report": bad, "notes": ""})
        self.assertEqual(r.status_code, 200)
        insp.refresh_from_db()
        self.assertFalse(insp.has_report)
        self.assertEqual(insp.status, "SCHEDULED")

    def test_ownership_isolation(self):
        insp = Inspection.objects.create(property=self.other_prop,
            inspection_date=timezone.localdate())
        self.assertEqual(self.client.get(
            reverse("inspections:detail", args=[insp.pk])).status_code, 404)
        # And the form only offers this owner's properties.
        r = self.client.get(reverse("inspections:create"))
        self.assertEqual(list(r.context["form"].fields["property"].queryset), [self.prop])

    def test_tenant_forbidden(self):
        User.objects.create_user("t@x.com", "t@x.com", "Pass!2345", role="TENANT")
        self.client.logout()
        self.client.login(username="t@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(reverse("inspections:list")).status_code, 403)
