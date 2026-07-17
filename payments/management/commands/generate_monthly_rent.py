"""
Management command: generate the current month's rent record for every
active lease (bonus feature).

Idempotent — the unique constraint on (lease, month, year) plus get_or_create
means running it twice does not create duplicates. Run on the 1st of each
month via cron / Task Scheduler:

    python manage.py generate_monthly_rent
    python manage.py generate_monthly_rent --month 8 --year 2026 --due-day 5
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from leases.models import Lease
from payments.models import RentPayment


class Command(BaseCommand):
    help = "Create pending rent records for all active leases for a given month."

    def add_arguments(self, parser):
        today = timezone.localdate()
        parser.add_argument("--month", type=int, default=today.month)
        parser.add_argument("--year", type=int, default=today.year)
        parser.add_argument("--due-day", type=int, default=5,
                            help="Day of the month rent is due (default 5).")

    def handle(self, *args, **options):
        month, year, due_day = options["month"], options["year"], options["due_day"]
        if not 1 <= month <= 12:
            raise CommandError("Month must be between 1 and 12.")
        try:
            due_date = date(year, month, due_day)
        except ValueError as exc:
            raise CommandError(f"Invalid due date: {exc}")

        created = skipped = 0
        for lease in Lease.objects.filter(status=Lease.Status.ACTIVE):
            _, was_created = RentPayment.objects.get_or_create(
                lease=lease, month=month, year=year,
                defaults={
                    "amount": lease.monthly_rent,
                    "due_date": due_date,
                    "status": RentPayment.Status.PENDING,
                },
            )
            created += was_created
            skipped += not was_created

        self.stdout.write(self.style.SUCCESS(
            f"Rent for {month:02d}/{year}: created {created}, "
            f"skipped {skipped} (already existed)."
        ))
