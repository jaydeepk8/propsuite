"""
Management command: warn about leases expiring soon (bonus feature).

Notifies both the tenant and the property owner for every active lease
ending within `--days` (default 30). Run daily:

    python manage.py send_lease_expiry_reminders --days 30
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from leases.models import Lease
from notifications.models import Notification
from notifications.services import notify, notify_many


class Command(BaseCommand):
    help = "Notify tenants and owners about leases expiring within N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30,
                            help="Look-ahead window in days (default 30).")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        days, dry = options["days"], options["dry_run"]
        today = timezone.localdate()
        window_end = today + timedelta(days=days)

        expiring = (Lease.objects.filter(status=Lease.Status.ACTIVE,
                                         end_date__gte=today,
                                         end_date__lte=window_end)
                    .select_related("tenant__user", "unit__property__owner"))

        count = 0
        for lease in expiring:
            remaining = (lease.end_date - today).days
            url = f"/leases/{lease.pk}/"
            if not dry:
                # Tenant gets an email; the owner just gets the in-app notice.
                notify(
                    lease.tenant.user,
                    f"Your lease expires in {remaining} day{'' if remaining == 1 else 's'}",
                    f"Unit {lease.unit.unit_number} at {lease.unit.property.title} "
                    f"ends on {lease.end_date:%b %d, %Y}. Contact your owner to renew.",
                    Notification.Kind.LEASE_EXPIRY, url, email=True,
                )
                notify(
                    lease.unit.property.owner,
                    f"Lease expiring: {lease.tenant.full_name}",
                    f"Unit {lease.unit.unit_number} ends on {lease.end_date:%b %d, %Y} "
                    f"({remaining} day{'' if remaining == 1 else 's'}).",
                    Notification.Kind.LEASE_EXPIRY, url,
                )
            count += 1

        prefix = "[dry-run] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Sent expiry reminders for {count} lease(s) ending within {days} day(s)."
        ))
