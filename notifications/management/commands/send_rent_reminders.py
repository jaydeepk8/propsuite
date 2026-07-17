"""
Management command: remind tenants about rent due soon (bonus feature).

Sends an in-app notification and an email to each tenant with a pending
payment falling due within `--days` (default 3). Run daily:

    python manage.py send_rent_reminders --days 3
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import Notification
from notifications.services import notify
from payments.models import RentPayment


class Command(BaseCommand):
    help = "Email/notify tenants whose rent falls due within N days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=3,
                            help="Look-ahead window in days (default 3).")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        days, dry = options["days"], options["dry_run"]
        today = timezone.localdate()
        window_end = today + timedelta(days=days)

        due_soon = (RentPayment.objects.pending()
                    .filter(due_date__gte=today, due_date__lte=window_end)
                    .select_related("lease__tenant__user", "lease__unit__property"))

        sent = 0
        for payment in due_soon:
            if not dry:
                notify(
                    payment.lease.tenant.user,
                    f"Rent reminder — {payment.period_label}",
                    f"₹{payment.total_due} for Unit {payment.lease.unit.unit_number} "
                    f"is due on {payment.due_date:%b %d, %Y}.",
                    Notification.Kind.RENT_DUE,
                    f"/payments/{payment.pk}/",
                    email=True,
                )
            sent += 1

        prefix = "[dry-run] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Sent {sent} rent reminder(s) for the next {days} day(s)."
        ))
