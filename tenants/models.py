"""Tenant profile model."""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse


class TenantQuerySet(models.QuerySet):
    """Scope tenants to what a given user is allowed to see."""

    def for_user(self, user):
        """
        Admins see all tenants. An owner sees tenants they onboarded plus any
        tenant leasing one of their units.
        """
        if user.is_admin:
            return self
        return self.filter(
            models.Q(created_by=user)
            | models.Q(leases__unit__property__owner=user)
        ).distinct()


class Tenant(models.Model):
    """
    Extended profile for a user with the Tenant role.

    Linked one-to-one with the auth user (which holds name/email/login).
    `created_by` records the owner who onboarded the tenant so they appear in
    that owner's list before any lease exists.
    """

    aadhaar_validator = RegexValidator(
        regex=r"^\d{12}$",
        message="Aadhaar must be exactly 12 digits.",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tenant_profile",
    )
    phone = models.CharField(max_length=16, blank=True)
    emergency_contact = models.CharField(max_length=16, blank=True)
    # NOTE: Aadhaar is sensitive PII — stored here for demo/coursework only.
    # In production this must be encrypted-at-rest or reduced to last 4 digits.
    aadhaar_number = models.CharField(
        max_length=12, blank=True, validators=[aadhaar_validator],
        help_text="Demo only — do not store real Aadhaar numbers.",
    )
    occupation = models.CharField(max_length=100, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="onboarded_tenants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantQuerySet.as_manager()

    class Meta:
        ordering = ["user__first_name", "user__username"]

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        return reverse("tenants:detail", kwargs={"pk": self.pk})

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        return self.user.email

    @property
    def masked_aadhaar(self):
        """Never render the full number; show only the last 4 digits."""
        if self.aadhaar_number:
            return f"XXXX XXXX {self.aadhaar_number[-4:]}"
        return "—"

    @property
    def active_lease(self):
        """The tenant's current active lease, if any."""
        return self.leases.filter(status="ACTIVE").select_related("unit__property").first()
