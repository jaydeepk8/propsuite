"""Test QR-code generation for properties (isolated to a temp media dir)."""

import shutil
import tempfile

from django.test import TestCase, override_settings

from accounts.models import User
from properties.models import Property

_TMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=_TMP_MEDIA, TESTING=False)
class PropertyQRTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")

    def _make(self):
        return Property.objects.create(
            owner=self.owner, title="Skyline", property_type="RESIDENTIAL",
            status="ACTIVE", address="1 St", city="Chicago", state="IL",
            country="USA", pincode="60601")

    def test_qr_generated_on_create(self):
        p = self._make()
        self.assertTrue(p.qr_code)
        self.assertTrue(p.qr_code.name.endswith(".png"))
        # File exists and is a real PNG.
        p.qr_code.open("rb")
        header = p.qr_code.read(8)
        p.qr_code.close()
        self.assertEqual(header[:4], b"\x89PNG")

    def test_qr_not_regenerated_on_resave(self):
        p = self._make()
        name = p.qr_code.name
        p.title = "Renamed"
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.qr_code.name, name)  # unchanged
