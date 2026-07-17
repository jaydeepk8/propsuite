"""
Signal receivers that turn domain events into notifications.

Kept in the notifications app (rather than scattered across payments /
maintenance / inspections) so every rule lives in one readable place.
Connected from NotificationsConfig.ready().
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from inspections.models import Inspection
from leases.models import Lease
from maintenance.models import MaintenanceRequest
from payments.models import RentPayment
from .models import Notification
from .services import notify, notify_many


def _stash_old(sender, instance, field, attr):
    """Remember a field's saved value so post_save can detect a transition."""
    old = None
    if instance.pk:
        old = (sender.objects.filter(pk=instance.pk)
               .values_list(field, flat=True).first())
    setattr(instance, attr, old)


# ── Payments ────────────────────────────────────────────
@receiver(pre_save, sender=RentPayment)
def payment_pre_save(sender, instance, **kwargs):
    _stash_old(sender, instance, "status", "_old_status")


@receiver(post_save, sender=RentPayment)
def payment_saved(sender, instance, created, **kwargs):
    url = reverse("payments:detail", kwargs={"pk": instance.pk})
    tenant_user = instance.lease.tenant.user
    owner = instance.lease.unit.property.owner

    # A freshly-billed month -> tell the tenant rent is due.
    if created and instance.status == RentPayment.Status.PENDING:
        notify(
            tenant_user,
            f"Rent due for {instance.period_label}",
            f"₹{instance.total_due} is due on {instance.due_date:%b %d, %Y}.",
            Notification.Kind.RENT_DUE, url,
        )
        return

    # Money landed -> tell the owner.
    became_paid = (instance.status == RentPayment.Status.PAID
                   and getattr(instance, "_old_status", None) != RentPayment.Status.PAID)
    if became_paid:
        notify(
            owner,
            f"Payment received — {instance.period_label}",
            f"{instance.lease.tenant.full_name} paid ₹{instance.total_due}.",
            Notification.Kind.PAYMENT_RECEIVED, url,
        )


# ── Maintenance ─────────────────────────────────────────
@receiver(pre_save, sender=MaintenanceRequest)
def maintenance_pre_save(sender, instance, **kwargs):
    _stash_old(sender, instance, "assigned_to_id", "_old_assignee")


@receiver(post_save, sender=MaintenanceRequest)
def maintenance_saved(sender, instance, created, **kwargs):
    url = reverse("maintenance:detail", kwargs={"pk": instance.pk})
    owner = instance.unit.property.owner

    # New ticket -> tell the property owner.
    if created:
        notify(
            owner,
            f"New maintenance request: {instance.title}",
            f"{instance.get_priority_display()} priority · "
            f"{instance.unit.property.title} · Unit {instance.unit.unit_number}",
            Notification.Kind.MAINTENANCE, url,
        )

    # Newly assigned -> tell the assignee (and the tenant who raised it).
    assignee_changed = (instance.assigned_to_id
                        and instance.assigned_to_id != getattr(instance, "_old_assignee", None))
    if assignee_changed:
        notify(
            instance.assigned_to,
            f"Maintenance assigned: {instance.title}",
            f"You've been assigned a {instance.get_priority_display().lower()}-priority "
            f"request on Unit {instance.unit.unit_number}.",
            Notification.Kind.MAINTENANCE, url,
        )
        if instance.tenant:
            notify(
                instance.tenant.user,
                f"Your request is being handled: {instance.title}",
                "An assignee has been allocated to your maintenance request.",
                Notification.Kind.MAINTENANCE, url,
            )


# ── Inspections ─────────────────────────────────────────
@receiver(post_save, sender=Inspection)
def inspection_saved(sender, instance, created, **kwargs):
    if not created:
        return

    url = reverse("inspections:detail", kwargs={"pk": instance.pk})
    target = instance.property.title
    if instance.unit_id:
        target += f" · Unit {instance.unit.unit_number}"

    recipients = [instance.property.owner, instance.inspector]

    # Loop in the sitting tenant when a specific leased unit is inspected.
    if instance.unit_id:
        active = (Lease.objects.filter(unit_id=instance.unit_id,
                                       status=Lease.Status.ACTIVE)
                  .select_related("tenant__user").first())
        if active:
            recipients.append(active.tenant.user)

    notify_many(
        recipients,
        "Inspection scheduled",
        f"{target} on {instance.inspection_date:%b %d, %Y}.",
        Notification.Kind.INSPECTION, url,
    )
