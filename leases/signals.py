"""
Signals that keep a Unit's status in sync with its leases.

Business rules (from the spec):
  * an ACTIVE lease makes its unit Occupied
  * when the lease is no longer active (expired/pending/deleted) and nothing
    else keeps the unit occupied, it returns to Available

We recompute from the source of truth (the unit's leases) rather than
toggling blindly, so the result is always consistent. Units under
Maintenance are left alone unless an active lease exists.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from properties.models import Unit
from .models import Lease


def sync_unit_status(unit):
    """Set the unit to Occupied/Available based on whether it has an active lease."""
    has_active = unit.leases.filter(status=Lease.Status.ACTIVE).exists()

    if has_active and unit.status != Unit.Status.OCCUPIED:
        unit.status = Unit.Status.OCCUPIED
        unit.save(update_fields=["status", "updated_at"])
    elif not has_active and unit.status == Unit.Status.OCCUPIED:
        # Only free a unit we previously occupied — never override Maintenance.
        unit.status = Unit.Status.AVAILABLE
        unit.save(update_fields=["status", "updated_at"])


@receiver(post_save, sender=Lease)
def lease_saved(sender, instance, **kwargs):
    sync_unit_status(instance.unit)


@receiver(post_delete, sender=Lease)
def lease_deleted(sender, instance, **kwargs):
    # The unit may already be gone if the whole property was deleted.
    try:
        unit = instance.unit
    except Unit.DoesNotExist:
        return
    sync_unit_status(unit)
