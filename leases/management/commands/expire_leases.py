"""
Management command: roll lease statuses forward based on today's date.

  * ACTIVE leases whose end_date has passed  -> EXPIRED  (frees the unit)
  * PENDING leases whose start_date has arrived and not yet ended -> ACTIVE
    (occupies the unit)

Unit status changes happen automatically via the lease signals. Run daily
(e.g. from cron / Task Scheduler):

    python manage.py expire_leases
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from leases.models import Lease


class Command(BaseCommand):
    help = "Expire past-due leases and activate leases whose term has started."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would change without saving.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        dry = options["dry_run"]

        to_expire = Lease.objects.filter(
            status=Lease.Status.ACTIVE, end_date__lt=today
        )
        to_activate = Lease.objects.filter(
            status=Lease.Status.PENDING,
            start_date__lte=today, end_date__gte=today,
        )

        expired = to_expire.count()
        activated = to_activate.count()

        if not dry:
            # Save individually so the post_save signal syncs each unit.
            for lease in to_expire:
                lease.status = Lease.Status.EXPIRED
                lease.save(update_fields=["status", "updated_at"])
            for lease in to_activate:
                lease.status = Lease.Status.ACTIVE
                lease.save(update_fields=["status", "updated_at"])

        prefix = "[dry-run] " if dry else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Expired {expired} lease(s), activated {activated} lease(s)."
        ))
