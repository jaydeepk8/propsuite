"""Custom manager for the PropSuite User model."""

from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    """
    User manager with role-aware convenience querysets.

    Extends Django's default UserManager so `create_user` /
    `create_superuser` keep working, while adding helpers used across
    dashboards and reports.
    """

    def owners(self):
        """Return all users with the Property Owner role."""
        return self.filter(role=self.model.Roles.OWNER)

    def tenants(self):
        """Return all users with the Tenant role."""
        return self.filter(role=self.model.Roles.TENANT)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Superusers are administrators of the platform.
        extra_fields.setdefault("role", self.model.Roles.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)
