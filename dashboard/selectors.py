"""
Dashboard data selectors.

All dashboard querying lives here so the views stay thin and each metric is
testable on its own. Every function is scoped to the requesting user.
"""

import calendar
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import User
from inspections.models import Inspection
from leases.models import Lease
from maintenance.models import MaintenanceRequest
from payments.models import RentPayment
from properties.models import Property, Unit
from tenants.models import Tenant

_MONEY = DecimalField(max_digits=12, decimal_places=2)
_ZERO = Decimal("0.00")


def _sum(qs, expr):
    """Sum an expression, returning Decimal('0.00') instead of None."""
    return qs.aggregate(
        t=Coalesce(Sum(expr, output_field=_MONEY), _ZERO, output_field=_MONEY)
    )["t"]


def _last_n_months(n=6):
    """[(year, month), …] oldest-first, ending with the current month."""
    today = timezone.localdate()
    buckets, y, m = [], today.year, today.month
    for _ in range(n):
        buckets.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(buckets))


def revenue_trend(payment_qs, months=6):
    """Collected rent per month for the Chart.js area chart."""
    buckets = _last_n_months(months)
    rows = (payment_qs.paid()
            .values("year", "month")
            .annotate(total=Coalesce(Sum(F("amount") + F("late_fee"), output_field=_MONEY),
                                     _ZERO, output_field=_MONEY)))
    lookup = {(r["year"], r["month"]): r["total"] for r in rows}
    return {
        "labels": [f"{calendar.month_abbr[m]} {str(y)[2:]}" for y, m in buckets],
        "values": [float(lookup.get(b, _ZERO)) for b in buckets],
    }


def _unit_breakdown(unit_qs):
    """Occupied / vacant / maintenance counts + occupancy rate."""
    agg = unit_qs.aggregate(
        total=Count("id"),
        occupied=Count("id", filter=Q(status=Unit.Status.OCCUPIED)),
        vacant=Count("id", filter=Q(status=Unit.Status.AVAILABLE)),
        maintenance=Count("id", filter=Q(status=Unit.Status.MAINTENANCE)),
    )
    total = agg["total"] or 0
    agg["occupancy_rate"] = round((agg["occupied"] / total) * 100, 1) if total else 0.0
    return agg


def owner_dashboard(user):
    """Metrics for the Owner dashboard (screenshot layout)."""
    today = timezone.localdate()

    properties = Property.objects.for_user(user)
    units = Unit.objects.filter(property__in=properties)
    leases = Lease.objects.for_user(user)
    payments = RentPayment.objects.for_user(user)
    requests = MaintenanceRequest.objects.for_user(user)

    breakdown = _unit_breakdown(units)
    overdue = payments.overdue()

    return {
        "stats": {
            "total_properties": properties.count(),
            # created_at is a DateTimeField — compare against an aware datetime,
            # not a date, or Django warns about naive comparison.
            "new_properties": properties.filter(
                created_at__gte=timezone.now() - timedelta(days=30)).count(),
            "occupied_units": breakdown["occupied"],
            "vacant_units": breakdown["vacant"],
            "occupancy_rate": breakdown["occupancy_rate"],
            "monthly_revenue": _sum(
                payments.paid().filter(year=today.year, month=today.month),
                F("amount") + F("late_fee")),
            "pending_rent": _sum(payments.pending(), F("amount")),
            "late_count": overdue.count(),
            "maintenance_open": requests.open().count(),
            "maintenance_urgent": requests.open().filter(
                priority=MaintenanceRequest.Priority.HIGH).count(),
        },
        "chart_revenue": revenue_trend(payments),
        "chart_occupancy": {
            "occupied": breakdown["occupied"],
            "vacant": breakdown["vacant"],
            "rate": breakdown["occupancy_rate"],
        },
        # Upcoming lease expiries — the next 90 days.
        "lease_expiries": (leases.filter(status=Lease.Status.ACTIVE,
                                         end_date__gte=today,
                                         end_date__lte=today + timedelta(days=90))
                           .select_related("tenant__user", "unit__property")
                           .order_by("end_date")[:5]),
        "recent_requests": (requests.open()
                            .select_related("unit__property")
                            .order_by("-created_at")[:4]),
        "recent_payments": (payments.paid()
                            .select_related("lease__tenant__user", "lease__unit__property")
                            .order_by("-payment_date")[:4]),
    }


def expense_trend(expense_qs, months=6):
    """Total expenses per month, aligned to the same buckets as revenue."""
    buckets = _last_n_months(months)
    rows = (expense_qs
            .values("date__year", "date__month")
            .annotate(total=Coalesce(Sum("amount", output_field=_MONEY),
                                     _ZERO, output_field=_MONEY)))
    lookup = {(r["date__year"], r["date__month"]): r["total"] for r in rows}
    return [float(lookup.get(b, _ZERO)) for b in buckets]


def occupancy_analytics(user):
    """Occupancy + income-vs-expense analytics (bonus feature)."""
    from expenses.models import Expense  # local import avoids app-load cycle

    properties = Property.objects.for_user(user)
    units = Unit.objects.filter(property__in=properties)
    payments = RentPayment.objects.for_user(user)
    expenses = Expense.objects.for_user(user)

    breakdown = _unit_breakdown(units)

    # Per-property occupancy for the bar chart.
    per_property = []
    for prop in properties.order_by("title"):
        b = _unit_breakdown(Unit.objects.filter(property=prop))
        per_property.append({
            "title": prop.title,
            "occupied": b["occupied"],
            "vacant": b["vacant"] + b["maintenance"],
            "rate": b["occupancy_rate"],
        })

    revenue = revenue_trend(payments)
    income_collected = _sum(payments.paid(), F("amount") + F("late_fee"))
    expense_total = _sum(expenses, F("amount"))

    return {
        "breakdown": breakdown,
        "per_property": per_property,
        "chart_status": {
            "occupied": breakdown["occupied"],
            "vacant": breakdown["vacant"],
            "maintenance": breakdown["maintenance"],
        },
        "chart_property_labels": [p["title"] for p in per_property],
        "chart_property_occupied": [p["occupied"] for p in per_property],
        "chart_property_vacant": [p["vacant"] for p in per_property],
        "chart_months": revenue["labels"],
        "chart_income": revenue["values"],
        "chart_expense": expense_trend(expenses),
        "totals": {
            "income": income_collected,
            "expense": expense_total,
            "net": income_collected - expense_total,
            "properties": properties.count(),
            "occupancy_rate": breakdown["occupancy_rate"],
        },
    }


def admin_dashboard(user):
    """Platform-wide metrics for the Admin dashboard."""
    today = timezone.localdate()

    units = Unit.objects.all()
    payments = RentPayment.objects.all()
    breakdown = _unit_breakdown(units)

    return {
        "stats": {
            "total_users": User.objects.count(),
            "total_owners": User.objects.filter(role=User.Roles.OWNER).count(),
            "total_tenants": User.objects.filter(role=User.Roles.TENANT).count(),
            "total_properties": Property.objects.count(),
            "occupied_units": breakdown["occupied"],
            "vacant_units": breakdown["vacant"],
            "occupancy_rate": breakdown["occupancy_rate"],
            "monthly_revenue": _sum(
                payments.paid().filter(year=today.year, month=today.month),
                F("amount") + F("late_fee")),
            "pending_maintenance": MaintenanceRequest.objects.open().count(),
        },
        "chart_revenue": revenue_trend(payments),
        "chart_occupancy": {
            "occupied": breakdown["occupied"],
            "vacant": breakdown["vacant"],
            "rate": breakdown["occupancy_rate"],
        },
        "recent_properties": (Property.objects.select_related("owner")
                              .order_by("-created_at")[:5]),
        "recent_requests": (MaintenanceRequest.objects.open()
                            .select_related("unit__property")
                            .order_by("-created_at")[:4]),
    }


def tenant_dashboard(user):
    """Metrics for the Tenant dashboard: their lease, rent and requests."""
    today = timezone.localdate()
    profile = getattr(user, "tenant_profile", None)

    if profile is None:
        # A self-registered tenant with no profile yet — show an empty state.
        return {"profile": None, "lease": None, "stats": {}, "payments": [], "requests": []}

    lease = (Lease.objects.filter(tenant=profile, status=Lease.Status.ACTIVE)
             .select_related("unit__property").first())
    payments = RentPayment.objects.filter(lease__tenant=profile)
    requests = MaintenanceRequest.objects.filter(
        Q(tenant=profile) | Q(created_by=user)).distinct()

    next_due = (payments.pending().filter(due_date__gte=today)
                .order_by("due_date").first())
    overdue = payments.overdue().order_by("due_date").first()

    return {
        "profile": profile,
        "lease": lease,
        "stats": {
            "next_due": next_due,
            "overdue": overdue,
            "amount_due": (next_due.total_due if next_due
                           else (overdue.total_due if overdue else _ZERO)),
            "days_to_expiry": lease.days_to_expiry if lease else None,
            "open_requests": requests.open().count(),
            "total_paid": _sum(payments.paid(), F("amount") + F("late_fee")),
        },
        "payments": (payments.select_related("lease__unit__property")
                     .order_by("-year", "-month")[:5]),
        "requests": requests.select_related("unit__property").order_by("-created_at")[:4],
        "inspections": (Inspection.objects.filter(unit=lease.unit).upcoming()[:3]
                        if lease else []),
    }
