"""Reusable template filters/tags for PropSuite."""

from django import template

register = template.Library()


@register.filter
def compact_money(value):
    """
    Format a number as a compact currency string.

    Examples: 185000 -> '$185k', 1200000 -> '$1.2M', 4500 -> '$4,500'.
    Used on property cards / stat tiles to match the product UI.
    """
    try:
        n = float(value)
    except (TypeError, ValueError):
        return value

    sign = "-" if n < 0 else ""
    n = abs(n)
    if n >= 1_000_000:
        return f"{sign}${n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{sign}${n / 1_000:.0f}k"
    return f"{sign}${n:,.0f}"


@register.simple_tag
def status_badge_class(status):
    """Map a Property/Unit status to a PropSuite badge CSS class."""
    return {
        "ACTIVE": "rw-badge-green",
        "OCCUPIED": "rw-badge-blue",
        "AVAILABLE": "rw-badge-green",
        "PENDING": "rw-badge-amber",
        "MAINTENANCE": "rw-badge-amber",
        "INACTIVE": "rw-badge-gray",
        "EXPIRED": "rw-badge-gray",
        # Payment statuses
        "PAID": "rw-badge-green",
        "OVERDUE": "rw-badge-red",
        # Maintenance statuses
        "OPEN": "rw-badge-blue",
        "ASSIGNED": "rw-badge-amber",
        "IN_PROGRESS": "rw-badge-amber",
        "COMPLETED": "rw-badge-green",
        # Maintenance priorities
        "HIGH": "rw-badge-red",
        "MEDIUM": "rw-badge-amber",
        "LOW": "rw-badge-gray",
        # Inspection statuses
        "SCHEDULED": "rw-badge-blue",
        "CANCELLED": "rw-badge-gray",
    }.get(status, "rw-badge-gray")


@register.simple_tag
def priority_border_color(priority):
    """Left-border colour for the request cards in the activity feed."""
    return {
        "HIGH": "var(--rw-red)",
        "MEDIUM": "var(--rw-amber)",
        "LOW": "var(--rw-muted)",
    }.get(priority, "var(--rw-muted)")
