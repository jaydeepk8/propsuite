"""User model and account-related models for PropSuite."""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse

from .managers import UserManager


class User(AbstractUser):
    """
    Custom user model for PropSuite.

    Extends Django's AbstractUser (keeping username/password/email and the
    full auth machinery) and adds a role, phone number and profile image.
    A single `role` field drives dashboard routing and permissions.
    """

    class Roles(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        OWNER = "OWNER", "Property Owner"
        TENANT = "TENANT", "Tenant"

    # Basic phone validation — allows an optional leading + and 9–15 digits.
    phone_validator = RegexValidator(
        regex=r"^\+?\d{9,15}$",
        message="Enter a valid phone number (9–15 digits, optional leading +).",
    )

    # Email is required and unique — it doubles as a contact channel.
    email = models.EmailField("email address", unique=True)
    phone = models.CharField(
        max_length=16,
        blank=True,
        validators=[phone_validator],
    )
    role = models.CharField(
        max_length=10,
        choices=Roles.choices,
        default=Roles.TENANT,
        help_text="Determines dashboard and permissions.",
    )
    profile_image = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True,
    )

    objects = UserManager()

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def get_absolute_url(self):
        return reverse("accounts:profile")

    # ── Role helpers (used in templates, mixins and decorators) ──
    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN or self.is_superuser

    @property
    def is_owner(self):
        return self.role == self.Roles.OWNER

    @property
    def is_tenant(self):
        return self.role == self.Roles.TENANT
