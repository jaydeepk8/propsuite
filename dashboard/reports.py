"""
Report definitions.

Each report declares its columns once and builds plain rows (lists aligned to
those columns). The HTML preview, CSV export and PDF export all consume that
same structure, so the three outputs can never drift apart.

Reports live in the dashboard app because they're cross-cutting analytics
rather than a domain of their own.
"""

import calendar
from datetime import datetime
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from maintenance.models import MaintenanceRequest
from payments.models import RentPayment
from properties.models import Property, Unit

_MONEY = DecimalField(max_digits=12, decimal_places=2)
_ZERO = Decimal("0.00")


def _money_sum(qs, expr):
    return qs.aggregate(
        t=Coalesce(Sum(expr, output_field=_MONEY), _ZERO, output_field=_MONEY)
    )["t"]


def _int(value, default=None):
    """Parse an int from query params, tolerating blanks and junk."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class BaseReport:
    """Common plumbing: filters, cached rows, filename."""

    # The report index passes these classes straight to the template. Django
    # auto-calls callables (and a class is callable), which would try to
    # instantiate the report with no args. This flag tells it not to.
    do_not_call_in_templates = True

    slug = ""
    title = ""
    description = ""
    icon = "bi-file-earmark-bar-graph"
    # Which filter widgets the template should show.
    filter_fields = ("property",)

    def __init__(self, user, params=None):
        self.user = user
        self.params = params or {}
        self._rows = None

    # ── filters ──
    @property
    def property_id(self):
        return _int(self.params.get("property"))

    @property
    def month(self):
        return _int(self.params.get("month"), timezone.localdate().month)

    @property
    def year(self):
        return _int(self.params.get("year"), timezone.localdate().year)

    def properties(self):
        """Properties this user may report on, honouring the property filter."""
        qs = Property.objects.for_user(self.user)
        if self.property_id:
            qs = qs.filter(pk=self.property_id)
        return qs

    # ── data ──
    @property
    def columns(self):
        raise NotImplementedError

    @property
    def rows(self):
        if self._rows is None:
            self._rows = list(self.build_rows())
        return self._rows

    def build_rows(self):
        raise NotImplementedError

    def summary(self):
        """[(label, value), …] shown as cards above the table."""
        return []

    def total_row(self):
        """Optional footer row aligned to `columns` (None entries render blank)."""
        return None

    @property
    def period_label(self):
        return ""

    @property
    def filename(self):
        stamp = timezone.localdate().isoformat()
        return f"propsuite-{self.slug}-{stamp}"


class MonthlyRentReport(BaseReport):
    """Every rent record for one month, with collection status."""

    slug = "monthly-rent"
    title = "Monthly Rent Report"
    description = "All rent records for a given month with collection status."
    icon = "bi-calendar-month"
    filter_fields = ("month", "year", "property")

    columns = [
        {"label": "Tenant", "align": "left"},
        {"label": "Property", "align": "left"},
        {"label": "Unit", "align": "left"},
        {"label": "Due Date", "align": "left"},
        {"label": "Rent", "align": "right"},
        {"label": "Late Fee", "align": "right"},
        {"label": "Total", "align": "right"},
        {"label": "Status", "align": "left"},
    ]

    def queryset(self):
        return (RentPayment.objects.for_user(self.user)
                .filter(month=self.month, year=self.year,
                        lease__unit__property__in=self.properties())
                .select_related("lease__tenant__user", "lease__unit__property")
                .order_by("lease__unit__property__title", "lease__unit__unit_number"))

    def build_rows(self):
        for p in self.queryset():
            yield [
                p.lease.tenant.full_name,
                p.lease.unit.property.title,
                p.lease.unit.unit_number,
                p.due_date.strftime("%b %d, %Y"),
                p.amount,
                p.late_fee,
                p.total_due,
                p.effective_status_display,
            ]

    def summary(self):
        qs = self.queryset()
        collected = _money_sum(qs.paid(), F("amount") + F("late_fee"))
        pending = _money_sum(qs.pending(), F("amount") + F("late_fee"))
        return [
            ("Records", qs.count()),
            ("Collected", collected),
            ("Outstanding", pending),
            ("Overdue", qs.overdue().count()),
        ]

    def total_row(self):
        qs = self.queryset()
        return [
            "TOTAL", "", "", "",
            _money_sum(qs, F("amount")),
            _money_sum(qs, F("late_fee")),
            _money_sum(qs, F("amount") + F("late_fee")),
            "",
        ]

    @property
    def period_label(self):
        return f"{calendar.month_name[self.month]} {self.year}"


class PropertyIncomeReport(BaseReport):
    """Income and occupancy rolled up per property for a year."""

    slug = "property-income"
    title = "Property Income Report"
    description = "Income and occupancy rolled up per property."
    icon = "bi-buildings"
    filter_fields = ("year", "property")

    columns = [
        {"label": "Property", "align": "left"},
        {"label": "City", "align": "left"},
        {"label": "Units", "align": "right"},
        {"label": "Occupied", "align": "right"},
        {"label": "Occupancy", "align": "right"},
        {"label": "Collected", "align": "right"},
        {"label": "Outstanding", "align": "right"},
    ]

    def build_rows(self):
        for prop in self.properties().order_by("title"):
            units = Unit.objects.filter(property=prop)
            total = units.count()
            occupied = units.filter(status=Unit.Status.OCCUPIED).count()
            payments = RentPayment.objects.filter(
                lease__unit__property=prop, year=self.year)
            yield [
                prop.title,
                prop.city,
                total,
                occupied,
                f"{round((occupied / total) * 100, 1) if total else 0.0}%",
                _money_sum(payments.paid(), F("amount") + F("late_fee")),
                _money_sum(payments.pending(), F("amount") + F("late_fee")),
            ]

    def summary(self):
        payments = RentPayment.objects.for_user(self.user).filter(
            lease__unit__property__in=self.properties(), year=self.year)
        units = Unit.objects.filter(property__in=self.properties())
        return [
            ("Properties", self.properties().count()),
            ("Total Units", units.count()),
            ("Collected", _money_sum(payments.paid(), F("amount") + F("late_fee"))),
            ("Outstanding", _money_sum(payments.pending(), F("amount") + F("late_fee"))),
        ]

    def total_row(self):
        rows = self.rows
        return [
            "TOTAL", "",
            sum(r[2] for r in rows),
            sum(r[3] for r in rows),
            "",
            sum((r[5] for r in rows), _ZERO),
            sum((r[6] for r in rows), _ZERO),
        ]

    @property
    def period_label(self):
        return str(self.year)


class PendingPaymentsReport(BaseReport):
    """Everything still owed, oldest first, with days overdue."""

    slug = "pending-payments"
    title = "Pending Payments Report"
    description = "Outstanding rent across the portfolio, oldest first."
    icon = "bi-exclamation-triangle"
    filter_fields = ("property",)

    columns = [
        {"label": "Tenant", "align": "left"},
        {"label": "Property", "align": "left"},
        {"label": "Unit", "align": "left"},
        {"label": "Period", "align": "left"},
        {"label": "Due Date", "align": "left"},
        {"label": "Amount", "align": "right"},
        {"label": "Days Overdue", "align": "right"},
    ]

    def queryset(self):
        return (RentPayment.objects.for_user(self.user).pending()
                .filter(lease__unit__property__in=self.properties())
                .select_related("lease__tenant__user", "lease__unit__property")
                .order_by("due_date"))

    def build_rows(self):
        today = timezone.localdate()
        for p in self.queryset():
            overdue_days = (today - p.due_date).days
            yield [
                p.lease.tenant.full_name,
                p.lease.unit.property.title,
                p.lease.unit.unit_number,
                p.period_label,
                p.due_date.strftime("%b %d, %Y"),
                p.total_due,
                overdue_days if overdue_days > 0 else 0,
            ]

    def summary(self):
        qs = self.queryset()
        return [
            ("Outstanding Records", qs.count()),
            ("Total Outstanding", _money_sum(qs, F("amount") + F("late_fee"))),
            ("Overdue Records", qs.overdue().count()),
            ("Overdue Amount", _money_sum(qs.overdue(), F("amount") + F("late_fee"))),
        ]

    def total_row(self):
        return ["TOTAL", "", "", "", "",
                _money_sum(self.queryset(), F("amount") + F("late_fee")), ""]

    @property
    def period_label(self):
        return "As of " + timezone.localdate().strftime("%b %d, %Y")


class MaintenanceExpenseReport(BaseReport):
    """Maintenance costs by request, for a year."""

    slug = "maintenance-expense"
    title = "Maintenance Expense Report"
    description = "Estimated maintenance spend by request."
    icon = "bi-wrench-adjustable"
    filter_fields = ("year", "property")

    columns = [
        {"label": "Request", "align": "left"},
        {"label": "Property", "align": "left"},
        {"label": "Unit", "align": "left"},
        {"label": "Priority", "align": "left"},
        {"label": "Status", "align": "left"},
        {"label": "Raised", "align": "left"},
        {"label": "Completed", "align": "left"},
        {"label": "Est. Cost", "align": "right"},
    ]

    def queryset(self):
        return (MaintenanceRequest.objects.for_user(self.user)
                .filter(unit__property__in=self.properties(),
                        created_at__year=self.year)
                .select_related("unit__property")
                .order_by("-created_at"))

    def build_rows(self):
        for r in self.queryset():
            yield [
                r.title,
                r.unit.property.title,
                r.unit.unit_number,
                r.get_priority_display(),
                r.get_status_display(),
                r.created_at.strftime("%b %d, %Y"),
                r.completed_date.strftime("%b %d, %Y") if r.completed_date else "—",
                r.estimated_cost if r.estimated_cost is not None else _ZERO,
            ]

    def summary(self):
        qs = self.queryset()
        return [
            ("Requests", qs.count()),
            ("Total Est. Cost", _money_sum(qs, F("estimated_cost"))),
            ("Completed", qs.filter(status=MaintenanceRequest.Status.COMPLETED).count()),
            ("Still Open", qs.open().count()),
        ]

    def total_row(self):
        return ["TOTAL", "", "", "", "", "", "",
                _money_sum(self.queryset(), F("estimated_cost"))]

    @property
    def period_label(self):
        return str(self.year)


# Registry — keeps URLs stable and the index page data-driven.
REPORTS = {
    r.slug: r for r in (
        MonthlyRentReport,
        PropertyIncomeReport,
        PendingPaymentsReport,
        MaintenanceExpenseReport,
    )
}
