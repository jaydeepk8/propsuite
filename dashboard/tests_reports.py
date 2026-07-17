"""Tests for reports: data correctness, CSV/PDF export, scoping, filters."""

import csv
import io
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
from dashboard.reports import (
    MaintenanceExpenseReport, MonthlyRentReport, PendingPaymentsReport,
    PropertyIncomeReport, REPORTS,
)

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


class MonthlyRentReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner, "1000")

    def test_rows_and_totals(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=today.month, year=today.year,
            due_date=today, amount=Decimal("1000"), late_fee=Decimal("50"),
            status="PAID", payment_date=today)
        report = MonthlyRentReport(self.owner, {"month": today.month, "year": today.year})
        self.assertEqual(len(report.rows), 1)
        row = report.rows[0]
        self.assertEqual(row[6], Decimal("1050"))       # total = rent + late fee
        self.assertEqual(row[7], "Paid")
        total = report.total_row()
        self.assertEqual(total[6], Decimal("1050"))     # footer total

    def test_scoped_to_owner(self):
        today = timezone.localdate()
        other = User.objects.create_user("o2", "o2@x.com", "p", role="OWNER")
        _, _, _, other_lease = build_world(other)
        RentPayment.objects.create(lease=other_lease, month=today.month, year=today.year,
            due_date=today, amount=Decimal("9999"), status="PAID", payment_date=today)
        report = MonthlyRentReport(self.owner, {"month": today.month, "year": today.year})
        self.assertEqual(len(report.rows), 0)  # other owner's payment excluded


class OtherReportsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "p", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner, "2000")

    def test_property_income_report(self):
        today = timezone.localdate()
        self.unit.status = "OCCUPIED"; self.unit.save()
        RentPayment.objects.create(lease=self.lease, month=1, year=today.year,
            due_date=today, amount=Decimal("2000"), status="PAID", payment_date=today)
        report = PropertyIncomeReport(self.owner, {"year": today.year})
        row = report.rows[0]
        self.assertEqual(row[0], self.prop.title)
        self.assertEqual(row[5], Decimal("2000"))  # collected

    def test_pending_payments_report_days_overdue(self):
        today = timezone.localdate()
        RentPayment.objects.create(lease=self.lease, month=1, year=2020,
            due_date=today - timedelta(days=7), amount=Decimal("2000"), status="PENDING")
        report = PendingPaymentsReport(self.owner, {})
        row = report.rows[0]
        self.assertEqual(row[5], Decimal("2000"))
        self.assertEqual(row[6], 7)  # days overdue

    def test_maintenance_expense_report(self):
        today = timezone.localdate()
        MaintenanceRequest.objects.create(unit=self.unit, title="Fix roof",
            priority="HIGH", status="COMPLETED", estimated_cost=Decimal("5000"))
        report = MaintenanceExpenseReport(self.owner, {"year": today.year})
        self.assertEqual(report.rows[0][7], Decimal("5000"))
        self.assertEqual(report.total_row()[7], Decimal("5000"))


class ReportExportViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("own", "own@x.com", "Pass!2345", role="OWNER")
        cls.prop, cls.unit, cls.tenant, cls.lease = build_world(cls.owner, "1500")
        today = timezone.localdate()
        RentPayment.objects.create(lease=cls.lease, month=today.month, year=today.year,
            due_date=today, amount=Decimal("1500"), status="PAID", payment_date=today)

    def setUp(self):
        self.client.login(username="own@x.com", password="Pass!2345")

    def test_index_lists_all_reports(self):
        r = self.client.get(reverse("dashboard:reports"))
        self.assertEqual(r.status_code, 200)
        for report_cls in REPORTS.values():
            self.assertContains(r, report_cls.title)

    def test_html_preview_renders(self):
        r = self.client.get(reverse("dashboard:report_detail", args=["monthly-rent"]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Monthly Rent Report")

    def test_unknown_report_404(self):
        self.assertEqual(self.client.get(
            reverse("dashboard:report_detail", args=["nope"])).status_code, 404)

    def test_csv_export(self):
        r = self.client.get(reverse("dashboard:report_detail", args=["monthly-rent"]) + "?format=csv")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn(".csv", r["Content-Disposition"])
        # The body parses as CSV and contains the header + a data row.
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8"))))
        flat = [cell for row in rows for cell in row]
        self.assertIn("Tenant", flat)
        self.assertIn("1500.00", flat)

    def test_pdf_export(self):
        r = self.client.get(reverse("dashboard:report_detail", args=["monthly-rent"]) + "?format=pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn(".pdf", r["Content-Disposition"])
        self.assertTrue(r.content.startswith(b"%PDF"))  # valid PDF signature
        self.assertGreater(len(r.content), 1000)

    def test_tenant_forbidden(self):
        User.objects.create_user("t@x.com", "t@x.com", "Pass!2345", role="TENANT")
        self.client.logout()
        self.client.login(username="t@x.com", password="Pass!2345")
        self.assertEqual(self.client.get(reverse("dashboard:reports")).status_code, 403)

    def test_month_filter_changes_data(self):
        # Current month has 1 record; a different month has none.
        other_month = 12 if timezone.localdate().month != 12 else 1
        r = self.client.get(reverse("dashboard:report_detail", args=["monthly-rent"])
                            + f"?month={other_month}&year=2019")
        self.assertContains(r, "No data for this period")
